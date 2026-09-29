"""Survivorship-safe membership filter."""
from __future__ import annotations

import pandas as pd


def members_at(membership: pd.DataFrame, as_of) -> pd.DataFrame:
    t = pd.Timestamp(as_of)
    valid_from = pd.to_datetime(membership["valid_from"])
    valid_to = pd.to_datetime(membership["valid_to"])
    return membership[(valid_from <= t) & (t <= valid_to)].copy()
