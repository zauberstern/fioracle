"""Layer 3: LPPLS crash-risk estimation with multi-window confidence."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import lppls

    LPPLS_AVAILABLE = True
except ImportError:
    LPPLS_AVAILABLE = False
    logger.warning("lppls package not installed. Layer 3 will return placeholder outputs.")


@dataclass
class LPPLSOutput:
    effective_date: pd.Timestamp
    lpp_confidence: float
    crash_window_start: pd.Timestamp | None
    crash_window_end: pd.Timestamp | None
    tc_estimate: pd.Timestamp | None
    filter_conditions_met: bool


class LPPLSEngine:
    def __init__(
        self,
        n_restarts: int = 25,
        window_sizes: list[int] | None = None,
        confidence_threshold: float = 0.6,
    ):
        self.n_restarts = n_restarts
        self.window_sizes = window_sizes or [60, 90, 120, 150, 180]
        self.confidence_threshold = confidence_threshold

    def _fit_single_window(self, prices: pd.Series, window_size: int) -> dict | None:
        if len(prices) < window_size:
            return None
        window_prices = prices.iloc[-window_size:]
        t = np.arange(len(window_prices), dtype=float)
        p = np.asarray(window_prices.values, dtype=float)
        if LPPLS_AVAILABLE:
            try:
                model = lppls.LPPLS(observations=np.column_stack([t, np.log(np.maximum(p, 1e-8))]))
                tc, m, w, _a, _b, _c1, _c2, _O, D = model.fit(
                    MAX_SEARCHES=self.n_restarts,
                )
                conditions_met = (0.1 < m < 0.9) and (6 < w < 13) and (D > 0.5)
                return {
                    "tc": tc,
                    "m": m,
                    "omega": w,
                    "conditions_met": bool(conditions_met),
                    "window_size": window_size,
                    "last_date": prices.index[-1],
                }
            except Exception as exc:
                logger.debug("LPPLS fit failed for window %s: %s", window_size, exc)
                return None

        # Lightweight surrogate when lppls is not installed: residual-growth filter
        logp = np.log(np.maximum(p, 1e-8))
        slope = np.polyfit(t, logp, 1)[0]
        osc = np.std(logp - np.polyval(np.polyfit(t, logp, 1), t))
        conditions_met = slope > 0 and osc > 0
        tc = float(len(t) + 10)
        return {
            "tc": tc,
            "m": 0.5,
            "omega": 8.0,
            "conditions_met": conditions_met,
            "window_size": window_size,
            "last_date": prices.index[-1],
        }

    def compute(self, prices: pd.Series, as_of_date: pd.Timestamp) -> LPPLSOutput:
        valid_prices = prices[prices.index <= as_of_date]
        if len(valid_prices) < min(self.window_sizes):
            return LPPLSOutput(
                effective_date=pd.Timestamp(as_of_date),
                lpp_confidence=0.0,
                crash_window_start=None,
                crash_window_end=None,
                tc_estimate=None,
                filter_conditions_met=False,
            )

        fits = []
        tc_estimates = []
        for window_size in self.window_sizes:
            if len(valid_prices) >= window_size:
                result = self._fit_single_window(valid_prices, window_size)
                if result is not None:
                    fits.append(result)
                    if result["conditions_met"]:
                        window_start = valid_prices.index[-window_size]
                        tc_date = pd.Timestamp(window_start) + timedelta(days=float(result["tc"]))
                        tc_estimates.append(tc_date)

        if not fits:
            return LPPLSOutput(
                effective_date=pd.Timestamp(as_of_date),
                lpp_confidence=0.0,
                crash_window_start=None,
                crash_window_end=None,
                tc_estimate=None,
                filter_conditions_met=False,
            )

        conditions_met_count = sum(1 for item in fits if item["conditions_met"])
        lpp_confidence = conditions_met_count / len(fits)
        if tc_estimates:
            tc_array = pd.to_datetime(tc_estimates)
            crash_window_start = pd.Timestamp(tc_array.min())
            crash_window_end = pd.Timestamp(tc_array.max())
            tc_estimate = pd.Timestamp(tc_array.to_series().median())
        else:
            crash_window_start = crash_window_end = tc_estimate = None

        return LPPLSOutput(
            effective_date=pd.Timestamp(as_of_date),
            lpp_confidence=float(lpp_confidence),
            crash_window_start=crash_window_start,
            crash_window_end=crash_window_end,
            tc_estimate=tc_estimate,
            filter_conditions_met=lpp_confidence >= self.confidence_threshold,
        )
