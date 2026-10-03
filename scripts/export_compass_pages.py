#!/usr/bin/env python3
"""Export Bubble Compass history parquet to static JSON for GitHub Pages."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LAYERS = ("dlinear", "bsadf", "lppls", "sentiment", "regime", "macro_debt")
DEFAULT_UNIVERSE = ROOT / "bubble_compass" / "game" / "src" / "data" / "universe.json"


def _assets_from_universe(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [str(s["id"]) for s in payload.get("sleeves", [])]


def _records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    # ISO dates, JSON-safe nulls (no NaN/Inf).
    out = json.loads(df.to_json(orient="records", date_format="iso"))
    return out


def export_asset(asset: str, history_root: Path, dest_dir: Path) -> dict:
    layers: dict[str, list] = {}
    for layer in LAYERS:
        path = history_root / layer / f"{asset}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        layers[layer] = _records(df)
    if not layers:
        raise FileNotFoundError(f"No history layers for {asset} under {history_root}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{asset}.json"
    payload = {"asset": asset, "layers": layers}
    out.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    return {
        "asset": asset,
        "path": str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out),
        "layers": sorted(layers.keys()),
        "n_rows": max((len(v) for v in layers.values()), default=0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--history",
        default=str(ROOT / "data" / "cache" / "history"),
        help="Root of history/{layer}/{asset}.parquet",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "docs" / "compass" / "data"),
        help="Destination docs/compass/data",
    )
    parser.add_argument("--universe", default=str(DEFAULT_UNIVERSE))
    parser.add_argument("--assets", nargs="+", default=None)
    args = parser.parse_args()

    history_root = Path(args.history)
    out_root = Path(args.out)
    hist_dir = out_root / "history"
    assets = args.assets or _assets_from_universe(Path(args.universe))

    manifest = []
    for asset in assets:
        entry = export_asset(asset, history_root, hist_dir)
        manifest.append(entry)
        print(f"exported {asset}: {entry['n_rows']} rows, layers={entry['layers']}")

    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "manifest.json").write_text(
        json.dumps(
            {
                "source": "history_parquet",
                "n_assets": len(manifest),
                "assets": manifest,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out_root / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
