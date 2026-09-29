"""Single observation contract for Bubble Compass (matches SeriesStore / wrds_ingest)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

OBSERVATION_COLUMNS = (
    "series_id",
    "event_date",
    "available_date",
    "value",
    "source",
)


def csv_to_observations(
    path: Path,
    *,
    series_id: str,
    publication_lag_days: int = 1,
    source: str = "landing_csv",
    value_col: Optional[str] = None,
) -> pd.DataFrame:
    if publication_lag_days < 0:
        raise ValueError("publication_lag_days must be >= 0 (negative lag is look-ahead)")
    path = Path(path)
    df = pd.read_csv(path)
    date_col = None
    for candidate in ("date", "Date", "DATE", "event_date", "effective_date"):
        if candidate in df.columns:
            date_col = candidate
            break
    if date_col is None:
        raise ValueError(f"No date column in {path}")
    if value_col is None:
        for candidate in ("value", "close", "adj_close", "price", "Value", "CLOSE"):
            if candidate in df.columns:
                value_col = candidate
                break
    if value_col is None:
        numeric = [c for c in df.columns if c != date_col and pd.api.types.is_numeric_dtype(df[c])]
        if not numeric:
            raise ValueError(f"No value column in {path}")
        value_col = numeric[0]

    out = pd.DataFrame(
        {
            "series_id": series_id,
            "event_date": pd.to_datetime(df[date_col]).dt.normalize(),
            "value": pd.to_numeric(df[value_col], errors="coerce"),
            "source": source,
        }
    )
    out["available_date"] = out["event_date"] + pd.to_timedelta(publication_lag_days, unit="D")
    out = out.dropna(subset=["value"]).sort_values("event_date")
    return out[list(OBSERVATION_COLUMNS)].reset_index(drop=True)


def frame_to_observations(
    df: pd.DataFrame,
    *,
    series_id: str,
    event_col: str,
    value_col: str,
    available_col: Optional[str] = None,
    source: str,
    publication_lag_days: int = 0,
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=list(OBSERVATION_COLUMNS))
    out = pd.DataFrame(
        {
            "series_id": series_id,
            "event_date": pd.to_datetime(df[event_col]).dt.normalize(),
            "value": pd.to_numeric(df[value_col], errors="coerce"),
            "source": source,
        }
    )
    if available_col and available_col in df.columns:
        out["available_date"] = pd.to_datetime(df[available_col]).dt.normalize()
    else:
        out["available_date"] = out["event_date"] + pd.to_timedelta(
            publication_lag_days, unit="D"
        )
    if (out["available_date"] < out["event_date"]).any():
        raise ValueError("PIT VIOLATION: available_date < event_date")
    return out[list(OBSERVATION_COLUMNS)].dropna(subset=["value"]).reset_index(drop=True)


def store_observations(
    obs: pd.DataFrame,
    *,
    store_dir: Path,
    data_type: str = "price",
) -> Path:
    """Write observation frame into PITStore layout (effective/knowledge rename)."""
    from bubble_compass.brain.data.pit_store import PITStore

    if obs.empty:
        raise ValueError("empty observations")
    series_id = str(obs["series_id"].iloc[0])
    frame = obs.rename(
        columns={"event_date": "effective_date", "available_date": "knowledge_date"}
    ).copy()
    frame["close"] = frame["value"]
    store = PITStore(Path(store_dir))
    store.store(frame, series_id, data_type)  # type: ignore[arg-type]
    return Path(store_dir) / data_type / f"{series_id}.parquet"
