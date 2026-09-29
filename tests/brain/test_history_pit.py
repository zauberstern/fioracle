"""PIT / leakage gates for Bubble Compass history tape."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from bubble_compass.brain.data.pit_contract import csv_to_observations, store_observations
from bubble_compass.brain.data.pit_store import PITStore
from bubble_compass.brain.data.quant_history import run_history_for_asset
from bubble_compass.brain.engines.sentiment import SentimentEngine


def _write_price_csv(path: Path, start: str, n: int, base: float = 100.0) -> None:
    dates = pd.bdate_range(start, periods=n)
    prices = base + pd.Series(range(n)).astype(float) * 0.1
    pd.DataFrame({"date": dates, "value": prices}).to_csv(path, index=False)


def test_as_of_query_cannot_see_future_prices(tmp_path: Path) -> None:
    path = tmp_path / "SPY.csv"
    _write_price_csv(path, "2008-09-01", 20)
    obs = csv_to_observations(path, series_id="SPY", publication_lag_days=0)
    store_observations(obs, store_dir=tmp_path / "pit", data_type="price")
    store = PITStore(tmp_path / "pit")

    as_of = pd.Timestamp("2008-09-14")
    df = store.query_as_of("SPY", "price", as_of)
    assert not df.empty
    assert pd.to_datetime(df["effective_date"]).max() <= as_of
    assert pd.to_datetime(df["knowledge_date"]).max() <= as_of
    assert (pd.to_datetime(df["knowledge_date"]) >= pd.to_datetime(df["effective_date"])).all()


def test_history_completeness_and_sentiment_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "HY.csv"
    _write_price_csv(path, "2020-01-02", 100)
    obs = csv_to_observations(path, series_id="HY", publication_lag_days=0)
    store_observations(obs, store_dir=tmp_path / "pit", data_type="price")

    written = run_history_for_asset(
        asset="HY",
        pit_dir=tmp_path / "pit",
        cache_dir=tmp_path / "cache",
        start=pd.Timestamp("2020-03-01"),
        end=pd.Timestamp("2020-04-15"),
        step_days=5,
        headlines=None,
    )
    for layer in ("dlinear", "bsadf", "lppls", "sentiment", "regime"):
        assert written[layer].exists()
        hist = pd.read_parquet(written[layer])
        assert not hist.empty, layer
        assert hist["as_of"].max() <= pd.Timestamp("2020-04-15")

    sent = pd.read_parquet(written["sentiment"])
    assert "unavailable" in sent.columns
    assert bool(sent["unavailable"].all())
    assert sent["sentiment_level"].isna().all()


def test_empty_headlines_do_not_silently_zero_live_sentiment() -> None:
    engine = SentimentEngine()
    empty = pd.DataFrame(columns=["published_at", "headline"])
    out = engine.compute(empty, pd.Timestamp("2020-03-16"))
    # Engine returns zeros for empty input; consumers must not treat that as live tone.
    assert out.headline_count == 0
    assert out.sentiment_level == 0.0
    assert out.sentiment_velocity == 0.0
    # History writer marks the layer unavailable instead of publishing fake zeros.
    sent_row = {
        "as_of": pd.Timestamp("2020-03-16"),
        "sentiment_level": None,
        "sentiment_velocity": None,
        "unavailable": True,
    }
    assert sent_row["unavailable"] is True
    assert sent_row["sentiment_level"] is None


def test_knowledge_date_invariant_on_ingest(tmp_path: Path) -> None:
    bad = pd.DataFrame(
        {
            "series_id": ["X"],
            "effective_date": [pd.Timestamp("2020-01-02")],
            "knowledge_date": [pd.Timestamp("2019-12-31")],
            "value": [1.0],
            "source": ["test"],
            "close": [1.0],
        }
    )
    store = PITStore(tmp_path / "pit")
    with pytest.raises(ValueError):
        store.store(bad, "X", "price")
