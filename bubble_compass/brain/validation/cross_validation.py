"""Purged walk-forward split generator."""
from __future__ import annotations

import pandas as pd


def walk_forward(index: pd.DatetimeIndex, train_years: int = 5, test_years: int = 1):
    dates = pd.DatetimeIndex(index).sort_values()
    if dates.empty:
        return
    start = dates.min()
    end = dates.max()
    cursor = start + pd.DateOffset(years=train_years)
    while cursor + pd.DateOffset(years=test_years) <= end + pd.Timedelta(days=1):
        train_end = cursor
        test_end = cursor + pd.DateOffset(years=test_years)
        train = dates[(dates >= start) & (dates < train_end)]
        test = dates[(dates >= train_end) & (dates < test_end)]
        yield train, test
        cursor = test_end
