"""Engine and API tests for Bubble Compass brain layers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from bubble_compass.brain.api.message_types import (
    BSADFStateDelta,
    BubbleConfirmedEvent,
    DLinearStateDelta,
)
from bubble_compass.brain.api.redis_manager import RedisWebSocketManager
from bubble_compass.brain.data.ingestion import DataIngestion
from bubble_compass.brain.data.pit_store import PITStore
from bubble_compass.brain.data.universe import members_at
from bubble_compass.brain.engines.dlinear import DLinearEngine
from bubble_compass.brain.engines.lppls_engine import LPPLSEngine
from bubble_compass.brain.engines.macro_debt import MacroDebtEngine
from bubble_compass.brain.engines.psy_bsadf import PSYBubbleTest
from bubble_compass.brain.engines.regime_rl import RegimeRLEngine, RegimeState
from bubble_compass.brain.engines.sentiment import SentimentEngine
from bubble_compass.brain.validation.ledger import TrialLedger
from bubble_compass.brain.validation.statistics import (
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
)


def _price_series(n: int = 120, explosive: bool = False) -> pd.Series:
    idx = pd.bdate_range("2020-01-01", periods=n)
    t = np.arange(n, dtype=float)
    if explosive:
        values = 100 * np.exp(0.02 * t + 0.0004 * t**2)
    else:
        rng = np.random.default_rng(0)
        values = 100 + np.cumsum(rng.normal(0, 0.4, size=n))
    return pd.Series(values, index=idx)


class DummyTicker:
    def history(self, start, end, auto_adjust=False):
        del end, auto_adjust
        idx = pd.bdate_range(start, periods=5)
        return pd.DataFrame(
            {
                "Open": 100.0,
                "High": 101.0,
                "Low": 99.0,
                "Close": [100, 101, 102, 101, 103],
                "Adj Close": [100, 101, 102, 101, 103],
                "Volume": 1_000,
            },
            index=idx,
        )


class DummyYF:
    def Ticker(self, ticker):
        del ticker
        return DummyTicker()


def test_ingestion_assigns_next_business_day_knowledge(tmp_path):
    df = DataIngestion().fetch_prices("SPY", "2020-01-01", yf_module=DummyYF())
    assert len(df) == 5
    first = pd.to_datetime(df.iloc[0]["effective_date"])
    known = pd.to_datetime(df.iloc[0]["knowledge_date"])
    assert known > first
    store = PITStore(tmp_path / "pit")
    store.store(df, "SPY", "price")
    tri = DataIngestion().compute_total_return_index(df)
    assert "tri" in tri.columns
    assert tri["tri"].iloc[-1] > 0


def test_universe_membership_is_as_of():
    membership = pd.DataFrame(
        {
            "instrument_id": ["LEH", "SPY"],
            "valid_from": ["2007-01-01", "1993-01-01"],
            "valid_to": ["2008-09-15", "2099-01-01"],
            "index_id": ["SPX", "SPX"],
        }
    )
    mid = members_at(membership, "2008-01-01")
    assert set(mid["instrument_id"]) == {"LEH", "SPY"}
    late = members_at(membership, "2010-01-01")
    assert list(late["instrument_id"]) == ["SPY"]


def test_dlinear_outputs_are_finite_after_fit():
    prices = _price_series(120)
    engine = DLinearEngine(kernel_size=25, lookback=96)
    engine.fit(prices)
    out = engine.predict(prices, prices.index[-1])
    assert np.isfinite(out.trend)
    assert np.isfinite(out.residual)
    batch = engine.batch_compute(prices, prices.index[-5], prices.index[-1])
    assert len(batch) >= 1
    assert set(batch.columns) >= {"effective_date", "trend", "residual", "residual_z"}


def test_dlinear_short_series_returns_nan():
    prices = _price_series(10)
    engine = DLinearEngine(kernel_size=25)
    out = engine.predict(prices, prices.index[-1])
    assert np.isnan(out.trend)


def test_psy_insufficient_data_is_not_a_bubble():
    prices = _price_series(15)
    out = PSYBubbleTest(n_simulations=3).test(prices, prices.index[-1])
    assert out.bubble_flag is False
    assert np.isnan(out.bsadf_stat)


def test_psy_caches_critical_values():
    prices = _price_series(24)
    tester = PSYBubbleTest(n_simulations=4, min_window=0.3)
    a = tester.test(prices, prices.index[-1])
    b = tester.test(prices, prices.index[-1])
    assert a.critical_value == b.critical_value
    assert np.isfinite(a.bsadf_stat)


def test_lppls_aggregates_window_confidence():
    prices = _price_series(90, explosive=True)
    engine = LPPLSEngine(n_restarts=2, window_sizes=[40, 50], confidence_threshold=0.1)
    out = engine.compute(prices, prices.index[-1])
    assert 0.0 <= out.lpp_confidence <= 1.0


def test_sentiment_velocity_from_pre_scored_headlines():
    dates = pd.bdate_range("2024-01-01", periods=8)
    df = pd.DataFrame(
        {
            "date": dates,
            "headline": ["h"] * 8,
            "sentiment_score": np.linspace(-0.2, 0.8, 8),
            "ticker": "SPY",
        }
    )
    out = SentimentEngine(velocity_window=3).compute(df, dates[-1], ticker="SPY")
    assert out.headline_count == 1
    assert out.sentiment_level == pytest.approx(0.8)
    assert out.sentiment_velocity != 0


def test_regime_heuristic_flags_boom_on_strong_features():
    rets = pd.Series(np.linspace(0.001, 0.01, 30))
    out = RegimeRLEngine().predict(
        dlinear_z=2.0,
        bsadf_stat=5.0,
        bsadf_cv=1.5,
        lppls_conf=0.8,
        sentiment_vel=0.5,
        returns=rets,
        as_of_date=pd.Timestamp("2024-01-01"),
    )
    assert out.regime_state in {RegimeState.BOOM, RegimeState.BUST, RegimeState.NORMAL}
    assert out.boom_probability >= 0
    assert out.regime_confidence > 0


def test_macro_debt_gap():
    out = MacroDebtEngine().compute(135.0, pd.Timestamp("2024-01-01"))
    assert out.gap == pytest.approx(25.0)
    assert out.threshold_breach is True


def test_message_schemas_roundtrip():
    delta = DLinearStateDelta(asset="SPY", trend=1.0, residual=0.1, residual_z=1.2)
    assert delta.layer == "dlinear"
    flag = BSADFStateDelta(asset="SPY", bsadf_stat=3.1, critical_value=2.0, bubble_flag=True)
    assert flag.bubble_flag is True
    event = BubbleConfirmedEvent(
        asset="SPY",
        bsadf_stat=4.0,
        critical_value=2.0,
        timestamp=datetime.now(timezone.utc),
    )
    assert event.event == "bubble_confirmed"


def test_redis_manager_in_memory_fanout():
    import asyncio

    class FakeWS:
        def __init__(self):
            self.texts = []

        async def send_text(self, data):
            self.texts.append(data)

    async def _run():
        mgr = RedisWebSocketManager(redis_url="redis://127.0.0.1:1")
        await mgr.connect()
        ws = FakeWS()
        await mgr.subscribe("SPY", ws)
        await mgr.publish("SPY", {"type": "state_delta", "asset": "SPY"})
        assert ws.texts
        await mgr.set_cached_state("SPY", {"trend": 1})
        cached = await mgr.get_cached_state("SPY")
        assert cached["trend"] == 1
        await mgr.unsubscribe("SPY", ws)
        await mgr.disconnect()

    asyncio.run(_run())


def test_fastapi_state_and_assets(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    (cache / "dlinear").mkdir(parents=True)
    (cache / "dlinear" / "SPY_latest.json").write_text(
        json.dumps({"trend": 100.0, "residual": 0.1, "residual_z": 0.2}),
        encoding="utf-8",
    )
    (cache / "manifest.json").write_text(json.dumps([{"asset": "SPY"}]), encoding="utf-8")
    monkeypatch.setenv("BUBBLE_COMPASS_CACHE", str(cache))
    from bubble_compass.brain.api import server as server_mod

    with TestClient(server_mod.app) as client:
        assets = client.get("/api/v1/assets")
        assert assets.status_code == 200
        assert assets.json()[0]["asset"] == "SPY"
        state = client.get("/api/v1/state/SPY")
        assert state.status_code == 200
        assert state.json()["state"]["dlinear"]["trend"] == 100.0
        missing = client.get("/api/v1/state/NOPE")
        assert missing.status_code == 404
        with client.websocket_connect("/ws/SPY") as ws:
            first = ws.receive_json()
            assert first["type"] in {"initial_state", "error"}
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"


def test_psr_dsr_bounded():
    psr = probabilistic_sharpe_ratio(0.5, 0.0, 252)
    dsr = deflated_sharpe_ratio(0.5, 0.2, 20, 252)
    assert 0 <= psr <= 1
    assert 0 <= dsr <= 1


def test_trial_ledger_counts(tmp_path):
    ledger = TrialLedger(tmp_path / "trials.jsonl")
    ledger.append({"sr_oos": 0.4})
    ledger.append({"sr_oos": 0.2})
    assert ledger.count() == 2
