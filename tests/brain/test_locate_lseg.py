"""Locate LSEG panels and register them under bronze without duplicating bytes."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from bubble_compass.brain.data.locate_lseg import locate_and_register_lseg


def test_locate_registers_symlink_manifest(tmp_path: Path) -> None:
    src = tmp_path / "data_v3" / "data" / "macro"
    src.mkdir(parents=True)
    pd.DataFrame({"date": ["2010-01-04"], "value": [1.0]}).to_parquet(
        src / "lseg_eq_spread.parquet", index=False
    )
    bronze = tmp_path / "data" / "lake" / "bronze" / "lseg_panels"
    manifest = locate_and_register_lseg(
        search_roots=[tmp_path / "data_v3"],
        bronze_dir=bronze,
    )
    assert (bronze / "manifest.json").is_file()
    payload = json.loads((bronze / "manifest.json").read_text(encoding="utf-8"))
    assert "lseg_eq_spread" in payload["panels"]
    link = bronze / "lseg_eq_spread.parquet"
    assert link.exists()
    assert manifest["n_registered"] >= 1
