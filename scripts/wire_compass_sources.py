#!/usr/bin/env python3
"""Ingest catalogued landing CSVs + macros into Bubble Compass PIT store."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bubble_compass.brain.data.pit_contract import csv_to_observations, store_observations

# Asset CSVs: knowledge = event (market close known next open → lag 1 business-ish day)
ASSET_LAG = 1
# Macros: conservative publication lag (matches FI config spirit)
MACRO_LAGS = {
    "US_DEBT_TO_GDP": 90,
    "US_INFLATION_RATE": 45,
    "US_UNEMPLOYMENT_RATE": 45,
    "US_GDP_GROWTH": 90,
    "US_M2_VELOCITY": 90,
    "VIX": 1,
    "US_HY_CORP_OAS_TOTAL_RETURN": 1,
    "GPRI": 1,
    "EPU": 1,
    "NAO": 5,
}


def _ingest_dir(
    directory: Path,
    *,
    store_dir: Path,
    data_type: str,
    default_lag: int,
    lag_map: dict[str, int] | None,
    series_filter: set[str] | None,
) -> list[str]:
    wired: list[str] = []
    if not directory.is_dir():
        return wired
    for path in sorted(directory.glob("*.csv")):
        sid = path.stem
        if series_filter is not None and sid not in series_filter:
            continue
        lag = (lag_map or {}).get(sid, default_lag)
        try:
            obs = csv_to_observations(
                path,
                series_id=sid,
                publication_lag_days=lag,
                source="landing_csv",
            )
            store_observations(obs, store_dir=store_dir, data_type=data_type)
            wired.append(sid)
        except Exception as exc:
            print(f"skip {sid}: {exc}")
    return wired


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", default=str(ROOT / "data" / "cache" / "pit"))
    parser.add_argument("--asset-dir", default=str(ROOT / "asset_universe"))
    parser.add_argument("--macro-dir", default=str(ROOT / "macro_universe"))
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Optional series_id allowlist",
    )
    parser.add_argument(
        "--wired-out",
        default=str(ROOT / "data" / "cache" / "wired_series.json"),
    )
    args = parser.parse_args()
    store_dir = Path(args.store)
    allow = set(args.only) if args.only else None

    assets = _ingest_dir(
        Path(args.asset_dir),
        store_dir=store_dir,
        data_type="price",
        default_lag=ASSET_LAG,
        lag_map=None,
        series_filter=allow,
    )
    macros = _ingest_dir(
        Path(args.macro_dir),
        store_dir=store_dir,
        data_type="macro",
        default_lag=30,
        lag_map=MACRO_LAGS,
        series_filter=allow,
    )
    wired = sorted(set(assets) | set(macros))
    out = Path(args.wired_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(wired, indent=2) + "\n", encoding="utf-8")
    print(f"wired {len(wired)} series → {store_dir} (list: {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
