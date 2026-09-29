"""Ingest external series and stamp PIT knowledge dates."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class DataIngestion:
    """Fetch and normalize external data into PIT-compliant format."""

    def fetch_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str | None = None,
        yf_module: Any | None = None,
    ) -> pd.DataFrame:
        try:
            import yfinance as yf_default
        except ImportError:  # pragma: no cover
            yf_default = None
        yf = yf_module or yf_default
        if yf is None:
            logger.warning("yfinance not installed")
            return pd.DataFrame()

        yf_ticker = yf.Ticker(ticker)
        hist = yf_ticker.history(start=start_date, end=end_date, auto_adjust=False)
        if hist is None or getattr(hist, "empty", True):
            logger.warning("No data returned for %s", ticker)
            return pd.DataFrame()

        hist = hist.reset_index()
        hist.columns = [str(c).lower().replace(" ", "_") for c in hist.columns]
        date_col = "date" if "date" in hist.columns else hist.columns[0]
        hist["effective_date"] = pd.to_datetime(hist[date_col]).dt.normalize()
        hist["knowledge_date"] = hist["effective_date"] + pd.offsets.BDay(1)

        close_col = "close" if "close" in hist.columns else hist.columns[-1]
        adj = "adj_close" if "adj_close" in hist.columns else close_col
        out = pd.DataFrame(
            {
                "effective_date": hist["effective_date"].dt.date,
                "knowledge_date": pd.to_datetime(hist["knowledge_date"]).dt.date,
                "open": hist["open"] if "open" in hist.columns else hist[close_col],
                "high": hist["high"] if "high" in hist.columns else hist[close_col],
                "low": hist["low"] if "low" in hist.columns else hist[close_col],
                "close": hist[close_col],
                "adj_close": hist[adj],
                "volume": hist["volume"] if "volume" in hist.columns else 0,
                "ticker": ticker,
            }
        )
        return out

    def fetch_fred_series(
        self,
        series_id: str,
        start_date: str,
        api_key: str | None = None,
    ) -> pd.DataFrame:
        del api_key
        try:
            import pandas_datareader.data as web

            df = web.DataReader(series_id, "fred", start_date)
            df = df.reset_index()
            df.columns = ["effective_date", "value"]
        except Exception:
            logger.warning("pandas_datareader not installed, using stub data")
            return pd.DataFrame(columns=["effective_date", "knowledge_date", "value"])

        df["knowledge_date"] = (pd.to_datetime(df["effective_date"]) + timedelta(days=5)).dt.date
        df["effective_date"] = pd.to_datetime(df["effective_date"]).dt.date
        return df

    def compute_total_return_index(
        self,
        prices: pd.DataFrame,
        dividends: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        df = prices.sort_values("effective_date").copy()
        df["price_return"] = df["close"].pct_change()
        if dividends is not None and not dividends.empty:
            df = df.merge(
                dividends[["effective_date", "amount"]],
                on="effective_date",
                how="left",
            )
            df["amount"] = df["amount"].fillna(0)
            df["div_yield"] = df["amount"] / df["close"].shift(1)
        else:
            df["div_yield"] = 0
        df["total_return"] = df["price_return"].fillna(0) + df["div_yield"].fillna(0)
        df["tri"] = (1 + df["total_return"]).cumprod()
        return df[["effective_date", "knowledge_date", "tri", "close"]]
