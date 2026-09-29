#!/usr/bin/env python3
"""Probe WRDS libraries + LSEG credential presence; write entitlements.json (no secrets)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bubble_compass.brain.data.entitlements import (
    DEFAULT_INVENTORY,
    probe_from_inventory_and_client,
    try_live_wrds_client,
    write_entitlements,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="WRDS/LSEG entitlement probe")
    parser.add_argument(
        "--out",
        default=str(ROOT / "data" / "cache" / "entitlements.json"),
    )
    parser.add_argument("--dotenv", default=str(ROOT / ".env"))
    parser.add_argument(
        "--lseg-credentials",
        default=str(ROOT / "config" / "lseg_credentials.yaml"),
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip live WRDS; use paper inventory only",
    )
    args = parser.parse_args()

    client = None if args.offline else try_live_wrds_client(Path(args.dotenv))
    result = probe_from_inventory_and_client(
        inventory=DEFAULT_INVENTORY,
        client=client,
        lseg_credential_path=Path(args.lseg_credentials),
    )
    if client is None:
        result.libraries.setdefault(
            "_connection",
            {"status": "offline_inventory" if args.offline else "no_live_client"},
        )
    out = write_entitlements(result, Path(args.out))
    print(f"wrote {out} ({len(result.libraries)} library keys); lseg={result.lseg.get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
