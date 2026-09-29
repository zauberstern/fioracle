"""Point-in-time store with dual timestamps.

INVARIANT: joins use direction='backward' on knowledge_time only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


class PITStore:
    """Stores time-series facts with knowledge_date vs effective_date."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        df: pd.DataFrame,
        asset_id: str,
        data_type: Literal["price", "fundamental", "sentiment", "macro"],
    ) -> None:
        if "knowledge_date" not in df.columns or "effective_date" not in df.columns:
            raise ValueError("DataFrame must include effective_date and knowledge_date")

        work = df.copy()
        work["effective_date"] = pd.to_datetime(work["effective_date"])
        work["knowledge_date"] = pd.to_datetime(work["knowledge_date"])
        if not (work["knowledge_date"] >= work["effective_date"]).all():
            violations = work[work["knowledge_date"] < work["effective_date"]]
            raise ValueError(
                "PIT VIOLATION: "
                f"{len(violations)} rows have knowledge_date < effective_date. "
                f"This would cause look-ahead bias. First violation: {violations.iloc[0].to_dict()}"
            )

        path = self.base_path / data_type / f"{asset_id}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pandas(work)
        pq.write_table(table, path, compression="zstd")

    def query_as_of(
        self,
        asset_id: str,
        data_type: str,
        as_of_date: pd.Timestamp,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        path = self.base_path / data_type / f"{asset_id}.parquet"
        if not path.exists():
            return pd.DataFrame()

        df = pd.read_parquet(path, columns=columns)
        as_of = pd.Timestamp(as_of_date).normalize()
        known = pd.to_datetime(df["knowledge_date"]).dt.normalize()
        df = df[known <= as_of]
        return df.sort_values("effective_date")

    def merge_asof_pit(
        self,
        decisions: pd.DataFrame,
        facts: pd.DataFrame,
        decision_date_col: str = "date",
        fact_knowledge_col: str = "knowledge_date",
    ) -> pd.DataFrame:
        left = decisions.copy()
        right = facts.copy()
        left[decision_date_col] = pd.to_datetime(left[decision_date_col])
        right[fact_knowledge_col] = pd.to_datetime(right[fact_knowledge_col])
        result = pd.merge_asof(
            left.sort_values(decision_date_col),
            right.sort_values(fact_knowledge_col),
            left_on=decision_date_col,
            right_on=fact_knowledge_col,
            direction="backward",
        )
        valid = result[fact_knowledge_col].isna() | (
            result[fact_knowledge_col] <= result[decision_date_col]
        )
        if not bool(valid.all()):
            raise AssertionError("PIT VIOLATION in merge_asof_pit - this should never happen")
        return result
