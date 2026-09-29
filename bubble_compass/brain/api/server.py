"""FastAPI brain serving cached quant state over REST and WebSocket."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from bubble_compass.brain.api.redis_manager import RedisWebSocketManager

logger = logging.getLogger(__name__)

manager: RedisWebSocketManager | None = None
cache_path: Path = Path("data/cache")
CACHE_ENV = "BUBBLE_COMPASS_CACHE"


def _cache_dir() -> Path:
    import os

    return Path(os.environ.get(CACHE_ENV, cache_path))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global manager
    manager = RedisWebSocketManager()
    await manager.connect()
    app.state.manager = manager
    yield
    await manager.disconnect()


app = FastAPI(
    title="Bubble Compass API",
    description="Real-time financial bubble detection and visualization backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/assets")
async def list_assets() -> list[dict]:
    manifest_path = _cache_dir() / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as handle:
            return json.load(handle)
    return []


@app.get("/api/v1/state/{asset}")
async def get_asset_state(asset: str) -> dict:
    state = {}
    for layer in ["dlinear", "bsadf", "lppls", "sentiment", "regime"]:
        layer_path = _cache_dir() / layer / f"{asset}_latest.json"
        if layer_path.exists():
            with open(layer_path, encoding="utf-8") as handle:
                state[layer] = json.load(handle)
    if not state:
        raise HTTPException(status_code=404, detail=f"Asset {asset} not found")
    return {
        "asset": asset,
        "state": state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


LAYERS = ("dlinear", "bsadf", "lppls", "sentiment", "regime", "macro_debt")


def _history_path(asset: str, layer: str) -> Path:
    return _cache_dir() / "history" / layer / f"{asset}.parquet"


def _records_as_of(df, as_of: str) -> dict:
    import pandas as pd

    if df.empty or "as_of" not in df.columns:
        return {}
    stamp = pd.to_datetime(as_of).normalize()
    known = pd.to_datetime(df["as_of"]).dt.normalize()
    subset = df[known <= stamp]
    if subset.empty:
        return {}
    row = subset.sort_values("as_of").iloc[-1]
    out = {}
    for key, val in row.items():
        if key == "as_of":
            continue
        if hasattr(val, "item"):
            try:
                val = val.item()
            except Exception:
                pass
        if pd.isna(val):
            out[key] = None
        elif hasattr(val, "isoformat"):
            out[key] = val.isoformat()
        else:
            out[key] = val
    out_as_of = pd.Timestamp(row["as_of"]).strftime("%Y-%m-%d")
    return {"as_of": out_as_of, "fields": out}


@app.get("/api/v1/history/{asset}")
async def get_layer_history(asset: str, start_date: str | None = None, end_date: str | None = None) -> dict:
    import pandas as pd

    layers: dict = {}
    for layer in LAYERS:
        path = _history_path(asset, layer)
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if "as_of" in df.columns:
            if start_date:
                df = df[pd.to_datetime(df["as_of"]) >= pd.Timestamp(start_date)]
            if end_date:
                df = df[pd.to_datetime(df["as_of"]) <= pd.Timestamp(end_date)]
            records = json.loads(df.to_json(orient="records", date_format="iso"))
            layers[layer] = records
    if not layers:
        raise HTTPException(status_code=404, detail=f"No history for {asset}")
    return {"asset": asset, "layers": layers}


@app.get("/api/v1/as-of/{asset}")
async def get_as_of_state(asset: str, date: str) -> dict:
    import pandas as pd

    state = {}
    resolved_as_of = None
    for layer in LAYERS:
        path = _history_path(asset, layer)
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        tip = _records_as_of(df, date)
        if not tip:
            continue
        state[layer] = tip["fields"]
        resolved_as_of = tip["as_of"]
    if not state:
        raise HTTPException(status_code=404, detail=f"No as-of state for {asset} at {date}")
    return {
        "asset": asset,
        "as_of": resolved_as_of,
        "requested": date,
        "state": state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/historical/{asset}")
async def get_historical_data(
    asset: str,
    start_date: str,
    end_date: str | None = None,
) -> dict:
    """Backward-compatible alias → /history."""
    return await get_layer_history(asset, start_date=start_date, end_date=end_date)


@app.websocket("/ws/{asset}")
async def websocket_endpoint(websocket: WebSocket, asset: str):
    await websocket.accept()
    mgr = manager or getattr(websocket.app.state, "manager", None)
    if mgr is None:
        await websocket.close(code=1011, reason="Server not ready")
        return
    await mgr.subscribe(asset, websocket)
    try:
        try:
            state = await get_asset_state(asset)
            await websocket.send_json({"type": "initial_state", **state})
        except HTTPException:
            await websocket.send_json({"type": "error", "message": f"Asset {asset} not found"})
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg.get("type") == "subscribe_additional":
                extra = msg.get("asset")
                if extra:
                    await mgr.subscribe(extra, websocket)
    except WebSocketDisconnect:
        logger.info("Client disconnected from %s", asset)
    finally:
        await mgr.unsubscribe(asset, websocket)


async def push_state_delta(asset: str, layer: str, data: dict) -> None:
    if manager:
        await manager.publish(asset, {"type": "state_delta", "layer": layer, "asset": asset, **data})


async def push_regime_event(asset: str, event_type: str, data: dict) -> None:
    if manager:
        await manager.publish(
            asset, {"type": "regime_event", "event": event_type, "asset": asset, **data}
        )
