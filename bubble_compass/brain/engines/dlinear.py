"""Layer 1: DLinear trend vs residual decomposition."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DLinearOutput:
    effective_date: pd.Timestamp
    trend: float
    residual: float
    residual_z: float
    forecast_horizon: int


class DLinearEngine:
    def __init__(
        self,
        kernel_size: int = 25,
        lookback: int = 96,
        forecast_horizon: int = 24,
    ):
        self.kernel_size = kernel_size
        self.lookback = lookback
        self.forecast_horizon = forecast_horizon
        self._trend_weights: np.ndarray | None = None
        self._seasonal_weights: np.ndarray | None = None
        self._residual_mean = 0.0
        self._residual_std = 1.0

    def _moving_average_decomposition(self, series: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        front_pad = (self.kernel_size - 1) // 2
        back_pad = self.kernel_size - 1 - front_pad
        padded = np.pad(series.astype(float), (front_pad, back_pad), mode="edge")
        kernel = np.ones(self.kernel_size) / self.kernel_size
        trend = np.convolve(padded, kernel, mode="valid")
        seasonal = series.astype(float) - trend
        return trend, seasonal

    def fit(self, prices: pd.Series) -> None:
        values = prices.values[-self.lookback :]
        if len(values) < self.lookback:
            raise ValueError(f"Insufficient data: need {self.lookback} points, got {len(values)}")
        trend, seasonal = self._moving_average_decomposition(values)
        self._trend_weights = np.polyfit(np.arange(len(trend)), trend, deg=1)
        self._seasonal_weights = np.polyfit(np.arange(len(seasonal)), seasonal, deg=1)
        self._residual_mean = float(seasonal.mean())
        self._residual_std = float(seasonal.std()) if seasonal.std() > 0 else 1.0

    def predict(self, prices: pd.Series, as_of_date: pd.Timestamp) -> DLinearOutput:
        valid_prices = prices[prices.index <= as_of_date]
        if len(valid_prices) < self.kernel_size:
            return DLinearOutput(
                effective_date=pd.Timestamp(as_of_date),
                trend=float("nan"),
                residual=float("nan"),
                residual_z=float("nan"),
                forecast_horizon=self.forecast_horizon,
            )
        values = valid_prices.values[-self.lookback :]
        trend, seasonal = self._moving_average_decomposition(values)
        current_residual = float(seasonal[-1])
        residual_z = (current_residual - self._residual_mean) / self._residual_std
        return DLinearOutput(
            effective_date=pd.Timestamp(as_of_date),
            trend=float(trend[-1]),
            residual=current_residual,
            residual_z=float(residual_z),
            forecast_horizon=self.forecast_horizon,
        )

    def batch_compute(
        self,
        prices: pd.Series,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> pd.DataFrame:
        results = []
        for date in pd.date_range(start_date, end_date, freq="B"):
            output = self.predict(prices, date)
            results.append(
                {
                    "effective_date": output.effective_date,
                    "trend": output.trend,
                    "residual": output.residual,
                    "residual_z": output.residual_z,
                }
            )
        return pd.DataFrame(results)
