#!/usr/bin/env python3
"""Register LSEG panels from data_v3 / New Volume into lake bronze/lseg_panels."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bubble_compass.brain.data.locate_lseg import locate_and_register_lseg


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bronze",
        default=str(ROOT / "data" / "lake" / "bronze" / "lseg_panels"),
    )
    parser.add_argument("--root", action="append", default=[])
    args = parser.parse_args()
    roots = [Path(p) for p in args.root] or [
        ROOT / "data" / "data_v3",
        Path("/run/media/kartik/New Volume/thesis_data"),
        Path("/run/media/kartik/New Volume/volsurf_data_lake"),
    ]
    manifest = locate_and_register_lseg(search_roots=roots, bronze_dir=Path(args.bronze))
    print(f"registered {manifest['n_registered']} panels → {args.bronze}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
