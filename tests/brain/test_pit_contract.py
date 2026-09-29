"""Unified PIT observation contract for Bubble Compass ingest."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from bubble_compass.brain.data.pit_contract import (
    OBSERVATION_COLUMNS,
    csv_to_observations,
    store_observations,
)


def test_csv_to_observations_stamps_knowledge_date(tmp_path: Path) -> None:
    path = tmp_path / "GOLD_SPOT_PRICE.csv"
    pd.DataFrame(
        {"date": ["2010-01-04", "2010-01-05"], "value": [1100.0, 1105.0]}
    ).to_csv(path, index=False)
    obs = csv_to_observations(path, series_id="GOLD_SPOT_PRICE", publication_lag_days=1)
    assert list(obs.columns) == list(OBSERVATION_COLUMNS)
    assert obs["series_id"].iloc[0] == "GOLD_SPOT_PRICE"
    assert pd.Timestamp(obs["available_date"].iloc[0]) == pd.Timestamp("2010-01-05")
    assert (obs["available_date"] >= obs["event_date"]).all()


def test_store_and_query_as_of_blocks_future(tmp_path: Path) -> None:
    from bubble_compass.brain.data.pit_store import PITStore

    path = tmp_path / "HY.csv"
    pd.DataFrame(
        {
            "date": ["2008-09-12", "2008-09-15", "2008-09-16"],
            "value": [1.0, 2.0, 3.0],
        }
    ).to_csv(path, index=False)
    obs = csv_to_observations(path, series_id="HY", publication_lag_days=0)
    store = PITStore(tmp_path / "pit")
    # Adapt observation frame to PITStore price schema
    frame = obs.rename(columns={"event_date": "effective_date", "available_date": "knowledge_date"})
    frame["close"] = frame["value"]
    store.store(frame, "HY", "price")
    known = store.query_as_of("HY", "price", pd.Timestamp("2008-09-14"))
    assert known["effective_date"].max() <= pd.Timestamp("2008-09-14")
    assert len(known) == 1


def test_csv_rejects_inverted_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "BAD.csv"
    pd.DataFrame({"date": ["2010-01-05"], "value": [1.0]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="publication_lag"):
        csv_to_observations(path, series_id="BAD", publication_lag_days=-1)
