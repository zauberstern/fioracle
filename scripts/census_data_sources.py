#!/usr/bin/env python3
"""Census landing CSVs, lake, data_v3, optional New Volume roots → CATALOG.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bubble_compass.brain.data.census import census_sources, write_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Bubble Compass data census")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument(
        "--out",
        default=str(ROOT / "data" / "cache" / "CATALOG.json"),
    )
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        help="Extra directory to census (repeatable)",
    )
    parser.add_argument(
        "--wired-from",
        default=None,
        help="Optional JSON list of wired series_ids",
    )
    args = parser.parse_args()
    root = Path(args.root)
    extras = [Path(p) for p in args.extra]
    # Default New Volume candidates when present.
    for candidate in (
        Path("/run/media/kartik/New Volume/thesis_data"),
        Path("/run/media/kartik/New Volume/volsurf_data_lake"),
    ):
        if candidate.is_dir() and candidate not in extras:
            extras.append(candidate)

    wired: set[str] = set()
    if args.wired_from and Path(args.wired_from).is_file():
        wired = set(json.loads(Path(args.wired_from).read_text(encoding="utf-8")))

    catalog = census_sources(
        root=root,
        extra_roots=extras,
        wired_series_ids=wired,
    )
    out = write_catalog(catalog, Path(args.out))
    print(
        f"wrote {out}: {catalog['n_entries']} entries, "
        f"{catalog['n_wired']} wired"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
