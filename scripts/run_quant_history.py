#!/usr/bin/env python3
"""Write expanding-window Bubble Compass layer history (PIT-safe)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bubble_compass.brain.data.quant_history import run_history_for_asset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--assets",
        nargs="+",
        default=["SP500_TOTAL_RETURN", "BBG_US_HIGH_YIELD_TOTAL_RETURN"],
    )
    parser.add_argument("--pit", default=str(ROOT / "data" / "cache" / "pit"))
    parser.add_argument("--cache", default=str(ROOT / "data" / "cache"))
    parser.add_argument("--start", default="2008-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--step-days", type=int, default=5)
    args = parser.parse_args()

    end = pd.Timestamp(args.end) if args.end else pd.Timestamp.today().normalize()
    start = pd.Timestamp(args.start)
    out = Path(args.cache) / "history_manifest.json"
    # Merge so partial re-runs do not drop previously built assets.
    by_asset: dict[str, dict] = {}
    if out.exists():
        try:
            for row in json.loads(out.read_text(encoding="utf-8")):
                if isinstance(row, dict) and row.get("asset"):
                    by_asset[str(row["asset"])] = row
        except json.JSONDecodeError:
            by_asset = {}

    for asset in args.assets:
        written = run_history_for_asset(
            asset=asset,
            pit_dir=Path(args.pit),
            cache_dir=Path(args.cache),
            start=start,
            end=end,
            step_days=args.step_days,
        )
        by_asset[asset] = {
            "asset": asset,
            "layers": {k: str(v) for k, v in written.items()},
            "start": str(start.date()),
            "end": str(end.date()),
        }
        print(f"history {asset}: {len(written)} layers")

    manifest = [by_asset[k] for k in sorted(by_asset)]
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    tip = Path(args.cache) / "manifest.json"
    tip.write_text(
        json.dumps(
            [{"asset": a, "as_of": str(end.date())} for a in sorted(by_asset)],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out} ({len(manifest)} assets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
