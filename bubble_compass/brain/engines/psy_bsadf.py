"""Layer 2: Phillips-Shi-Yu backward sup-ADF bubble test."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class BSADFOutput:
    effective_date: pd.Timestamp
    bsadf_stat: float
    critical_value: float
    bubble_flag: bool
    p_value: float


class PSYBubbleTest:
    def __init__(
        self,
        min_window: float = 0.05,
        adf_lags: int = 1,
        n_simulations: int = 2000,
        window_stride: int = 1,
    ):
        self.min_window = min_window
        self.adf_lags = adf_lags
        self.n_simulations = n_simulations
        # Stride > 1 sparsifies recursive windows for long history jobs.
        self.window_stride = max(1, int(window_stride))
        self._critical_values: dict[tuple[int, float], float] = {}

    def _adf_statistic(self, y: np.ndarray, lags: int = 1) -> float:
        n = len(y)
        if n < lags + 3:
            return float("nan")
        dy = np.diff(y)
        y_lag = y[lags:-1]
        cols = [np.ones(len(y_lag)), y_lag]
        for j in range(1, lags + 1):
            lagged = dy[lags - j : lags - j + len(y_lag)]
            if len(lagged) != len(y_lag):
                lagged = np.resize(lagged, len(y_lag))
            cols.append(lagged)
        X = np.column_stack(cols)
        Y = dy[lags:]
        min_len = min(len(Y), X.shape[0])
        Y = Y[:min_len]
        X = X[:min_len]
        try:
            beta, residuals, _rank, _s = np.linalg.lstsq(X, Y, rcond=None)
            if residuals.size > 0:
                sigma2 = residuals[0] / max(len(Y) - X.shape[1], 1)
            else:
                sigma2 = float(np.var(Y - X @ beta))
            xtx_inv = np.linalg.inv(X.T @ X)
            var_beta = float(max(sigma2, 1e-12) * xtx_inv[1, 1])
            if not np.isfinite(var_beta) or var_beta <= 0:
                return float("nan")
            se_beta = np.sqrt(var_beta)
            return float(beta[1] / se_beta)
        except (np.linalg.LinAlgError, ValueError):
            return float("nan")

    def _bsadf_statistic(self, y: np.ndarray) -> float:
        T = len(y)
        r0 = max(int(self.min_window * T), self.adf_lags + 3)
        stride = self.window_stride
        bsadf = -np.inf
        r2_grid = list(range(r0, T, stride))
        if not r2_grid or r2_grid[-1] != T - 1:
            r2_grid.append(T - 1)
        for r2 in r2_grid:
            sadf_r2 = -np.inf
            r1_grid = list(range(0, r2 - r0 + 1, stride))
            if not r1_grid or r1_grid[-1] != r2 - r0:
                r1_grid.append(max(0, r2 - r0))
            for r1 in r1_grid:
                adf_stat = self._adf_statistic(y[r1 : r2 + 1], self.adf_lags)
                if not np.isnan(adf_stat):
                    sadf_r2 = max(sadf_r2, adf_stat)
            bsadf = max(bsadf, sadf_r2)
        return float(bsadf)

    def _simulate_critical_value(self, T: int, significance: float = 0.05) -> float:
        # Bucket by length so expanding-window history reuses one MC draw.
        key = (int(T // 20) * 20, round(significance, 3))
        if key in self._critical_values:
            return self._critical_values[key]
        if self.n_simulations <= 0:
            # Phillips-Shi-Yu asymptotic 5% BSADF critical value (approx).
            cv = 1.49 if significance >= 0.05 else 2.0
            self._critical_values[key] = cv
            return cv
        rng = np.random.default_rng(42)
        bsadf_null = []
        # Simulate at bucket mid-length once; reuse across nearby T.
        sim_T = max(key[0], 40)
        for _ in range(self.n_simulations):
            rw = np.cumsum(rng.standard_normal(sim_T))
            stat = self._bsadf_statistic(rw)
            if not np.isinf(stat) and not np.isnan(stat):
                bsadf_null.append(stat)
        cv = float(np.percentile(bsadf_null, (1 - significance) * 100)) if bsadf_null else 1.49
        self._critical_values[key] = cv
        return cv

    def test(
        self,
        prices: pd.Series,
        as_of_date: pd.Timestamp,
        significance: float = 0.05,
    ) -> BSADFOutput:
        valid_prices = prices[prices.index <= as_of_date]
        y = np.asarray(valid_prices.values, dtype=float)
        if len(y) < 20:
            return BSADFOutput(
                effective_date=pd.Timestamp(as_of_date),
                bsadf_stat=float("nan"),
                critical_value=float("nan"),
                bubble_flag=False,
                p_value=1.0,
            )
        bsadf_stat = self._bsadf_statistic(y)
        critical_value = self._simulate_critical_value(len(y), significance)
        bubble_flag = bool(bsadf_stat > critical_value)
        p_value = float(1.0 - stats.norm.cdf(bsadf_stat))
        return BSADFOutput(
            effective_date=pd.Timestamp(as_of_date),
            bsadf_stat=float(bsadf_stat),
            critical_value=float(critical_value),
            bubble_flag=bubble_flag,
            p_value=p_value,
        )
