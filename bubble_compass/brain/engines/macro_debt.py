"""Layer M: sovereign debt vs a sustainable-bubble threshold."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class MacroDebtOutput:
    effective_date: pd.Timestamp
    debt_to_gdp: float
    sustainable_threshold: float
    gap: float
    threshold_breach: bool


class MacroDebtEngine:
    def __init__(self, sustainable_threshold: float = 110.0, breach_gap: float = 20.0):
        self.sustainable_threshold = sustainable_threshold
        self.breach_gap = breach_gap

    def compute(self, debt_to_gdp: float, as_of_date: pd.Timestamp) -> MacroDebtOutput:
        gap = float(debt_to_gdp) - self.sustainable_threshold
        return MacroDebtOutput(
            effective_date=pd.Timestamp(as_of_date),
            debt_to_gdp=float(debt_to_gdp),
            sustainable_threshold=self.sustainable_threshold,
            gap=gap,
            threshold_breach=gap >= self.breach_gap,
        )
