"""Disk census emits CATALOG.json with path, rows, span, wired flag."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from bubble_compass.brain.data.census import census_sources, write_catalog


def test_census_landing_csvs_and_wired_flag(tmp_path: Path) -> None:
    asset_dir = tmp_path / "asset_universe"
    asset_dir.mkdir()
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2010-01-04", "2010-01-05"]),
            "value": [100.0, 101.0],
        }
    )
    frame.to_csv(asset_dir / "BBG_US_HIGH_YIELD_TOTAL_RETURN.csv", index=False)

    macro_dir = tmp_path / "macro_universe"
    macro_dir.mkdir()
    pd.DataFrame(
        {"date": ["2010-01-01"], "value": [90.0]}
    ).to_csv(macro_dir / "US_DEBT_TO_GDP.csv", index=False)

    lake = tmp_path / "data" / "lake" / "bronze" / "observations" / "series_id=US_HY"
    lake.mkdir(parents=True)
    pd.DataFrame(
        {
            "series_id": ["US_HY"],
            "event_date": pd.to_datetime(["2010-01-04"]),
            "available_date": pd.to_datetime(["2010-01-05"]),
            "value": [1.0],
            "source": ["csv"],
        }
    ).to_parquet(lake / "data.parquet", index=False)

    catalog = census_sources(
        root=tmp_path,
        asset_dir=asset_dir,
        macro_dir=macro_dir,
        lake_dir=tmp_path / "data" / "lake",
        data_v3_dir=tmp_path / "missing_v3",
        extra_roots=[],
        wired_series_ids={"US_HY"},
    )
    assert any(e["series_id"] == "BBG_US_HIGH_YIELD_TOTAL_RETURN" for e in catalog["entries"])
    hy = next(e for e in catalog["entries"] if e["series_id"] == "BBG_US_HIGH_YIELD_TOTAL_RETURN")
    assert hy["rows"] == 2
    assert hy["wired"] is False
    lake_entry = next(e for e in catalog["entries"] if e["series_id"] == "US_HY")
    assert lake_entry["wired"] is True

    out = write_catalog(catalog, tmp_path / "CATALOG.json")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert "entries" in loaded
    assert len(loaded["entries"]) >= 2
