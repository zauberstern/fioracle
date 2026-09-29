"""Tests for PIT store - these MUST pass before any other development."""

import pandas as pd
import pytest

from bubble_compass.brain.data.pit_store import PITStore


class TestPITStore:
    @pytest.fixture
    def store(self, tmp_path):
        return PITStore(tmp_path / "pit_data")

    def test_rejects_future_knowledge(self, store):
        """Knowledge date before effective date is a look-ahead bias violation."""
        df = pd.DataFrame(
            {
                "effective_date": ["2024-01-15"],
                "knowledge_date": ["2024-01-14"],
                "close": [100.0],
            }
        )
        with pytest.raises(ValueError, match="PIT VIOLATION"):
            store.store(df, "TEST", "price")

    def test_accepts_valid_pit_data(self, store):
        """Valid PIT data: knowledge >= effective."""
        df = pd.DataFrame(
            {
                "effective_date": ["2024-01-15", "2024-01-16"],
                "knowledge_date": ["2024-01-16", "2024-01-17"],
                "close": [100.0, 101.0],
            }
        )
        store.store(df, "TEST", "price")

        result = store.query_as_of("TEST", "price", pd.Timestamp("2024-01-16"))
        assert len(result) == 1
        assert result.iloc[0]["close"] == 100.0

    def test_merge_asof_pit_prevents_lookahead(self, store):
        """merge_asof_pit must never join future data."""
        decisions = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-16", "2024-01-17"]),
                "signal": [1, -1],
            }
        )
        facts = pd.DataFrame(
            {
                "knowledge_date": pd.to_datetime(["2024-01-15", "2024-01-17"]),
                "macro_value": [5.0, 6.0],
            }
        )

        result = store.merge_asof_pit(decisions, facts)

        assert (
            result.loc[result["date"] == pd.Timestamp("2024-01-16"), "macro_value"].iloc[0] == 5.0
        )
        assert (
            result.loc[result["date"] == pd.Timestamp("2024-01-17"), "macro_value"].iloc[0] == 6.0
        )
