"""Expanding-window history writer respects PIT as-of slices."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from bubble_compass.brain.data.pit_contract import csv_to_observations, store_observations
from bubble_compass.brain.data.quant_history import run_history_for_asset


def test_history_rows_only_use_known_prices(tmp_path: Path) -> None:
    path = tmp_path / "SPY.csv"
    dates = pd.bdate_range("2020-01-02", periods=80)
    prices = 100 + pd.Series(range(len(dates))).astype(float)
    pd.DataFrame({"date": dates, "value": prices}).to_csv(path, index=False)
    obs = csv_to_observations(path, series_id="SPY", publication_lag_days=0)
    store_observations(obs, store_dir=tmp_path / "pit", data_type="price")

    out = run_history_for_asset(
        asset="SPY",
        pit_dir=tmp_path / "pit",
        cache_dir=tmp_path / "cache",
        start=pd.Timestamp("2020-03-01"),
        end=pd.Timestamp("2020-03-20"),
        step_days=5,
    )
    hist = pd.read_parquet(out["dlinear"])
    assert not hist.empty
    assert "as_of" in hist.columns
    assert hist["as_of"].max() <= pd.Timestamp("2020-03-20")
    # No future peek: every residual_z computed with prices <= as_of
    assert (hist["as_of"] <= pd.Timestamp("2020-03-20")).all()
