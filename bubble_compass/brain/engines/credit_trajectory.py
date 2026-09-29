"""Part D: credit disagreement and trajectory features from market series."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from bubble_compass.brain.engines.tone_vs_market import compute_tone_vs_market_gap

PILLAR_KEYS = (
    "liquidity",
    "covenant",
    "refinancing",
    "downgrade",
    "legal",
)


@dataclass
class PDDisagreementPoint:
    issuer: str
    model_pd: float
    market_pd: float
    exposure: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "issuer": self.issuer,
            "model_pd": self.model_pd,
            "market_pd": self.market_pd,
            "exposure": self.exposure,
            "gap_bps": (self.market_pd - self.model_pd) * 10_000.0,
        }


@dataclass
class CliffMapPoint:
    issuer: str
    months_to_wall: float
    cost_to_ebitda: float
    debt_outstanding: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "issuer": self.issuer,
            "months_to_wall": self.months_to_wall,
            "cost_to_ebitda": self.cost_to_ebitda,
            "debt_outstanding": self.debt_outstanding,
        }


@dataclass
class CreditTrajectoryOutput:
    effective_date: pd.Timestamp
    tone_vs_market_gap: dict[str, Any]
    pd_disagreement: dict[str, Any]
    credit_surface: dict[str, Any]
    cliff_map: dict[str, Any]
    breach_calendar: dict[str, Any]
    stress_language: dict[str, Any]
    unavailable: bool = False
    missing_inputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "effective_date": self.effective_date.isoformat(),
            "unavailable": self.unavailable,
            "missing_inputs": self.missing_inputs,
            "tone_vs_market_gap": self.tone_vs_market_gap,
            "pd_disagreement": self.pd_disagreement,
            "credit_surface": self.credit_surface,
            "cliff_map": self.cliff_map,
            "breach_calendar": self.breach_calendar,
            "stress_language": self.stress_language,
        }


def _unavailable_block(reason: str) -> dict[str, Any]:
    return {"unavailable": True, "reason": reason}


def compute_pd_disagreement_points(
    rows: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    if not rows:
        return _unavailable_block("no issuer PD rows (CDS/Compustat absent)")
    points: list[dict[str, Any]] = []
    for row in rows:
        issuer = row.get("issuer")
        model_pd = row.get("model_pd")
        market_pd = row.get("market_pd")
        exposure = row.get("exposure")
        if issuer is None or model_pd is None or market_pd is None or exposure is None:
            continue
        pt = PDDisagreementPoint(
            issuer=str(issuer),
            model_pd=float(model_pd),
            market_pd=float(market_pd),
            exposure=float(exposure),
        )
        points.append(pt.to_dict())
    if not points:
        return _unavailable_block("issuer rows missing model_pd, market_pd, or exposure")
    return {"unavailable": False, "points": points}


def compute_credit_surface_steepening(
    spread_bps: Sequence[float] | pd.Series | None,
    ltv: Sequence[float] | pd.Series | None,
    *,
    steepening_threshold: float = 0.35,
) -> dict[str, Any]:
    if spread_bps is None or ltv is None:
        return _unavailable_block("spread and LTV series required")
    s = np.asarray(spread_bps, dtype=float)
    l = np.asarray(ltv, dtype=float)
    if s.size < 3 or l.size < 3 or s.size != l.size:
        return _unavailable_block("need aligned spread/LTV with at least 3 observations")
    if np.any(~np.isfinite(s)) or np.any(~np.isfinite(l)):
        return _unavailable_block("non-finite spread or LTV values")
    slope, _intercept = np.polyfit(l, s, 1)
    steepening = bool(slope >= steepening_threshold)
    return {
        "unavailable": False,
        "slope_bps_per_ltv": float(slope),
        "steepening_flag": steepening,
        "spread_bps": s.tolist(),
        "ltv": l.tolist(),
    }


def compute_cliff_map_points(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    yield_shock_bps: float = 0.0,
    shock_cost_multiplier: float = 0.15,
) -> dict[str, Any]:
    if not rows:
        return _unavailable_block("no maturity wall / leverage rows")
    shocked: list[dict[str, Any]] = []
    for row in rows:
        issuer = row.get("issuer")
        months = row.get("months_to_wall")
        cost = row.get("cost_to_ebitda")
        if issuer is None or months is None or cost is None:
            continue
        base_cost = float(cost)
        adj = base_cost * (1.0 + shock_cost_multiplier * float(yield_shock_bps) / 100.0)
        shocked.append(
            CliffMapPoint(
                issuer=str(issuer),
                months_to_wall=float(months),
                cost_to_ebitda=adj,
                debt_outstanding=(
                    float(row["debt_outstanding"]) if row.get("debt_outstanding") is not None else None
                ),
            ).to_dict()
        )
    if not shocked:
        return _unavailable_block("cliff rows missing issuer, months_to_wall, or cost_to_ebitda")
    return {
        "unavailable": False,
        "yield_shock_bps": float(yield_shock_bps),
        "points": shocked,
    }


def compute_breach_calendar_grid(
    grid: Sequence[Sequence[Any]] | None,
    *,
    quarters: Sequence[str] | None = None,
    covenants: Sequence[str] | None = None,
) -> dict[str, Any]:
    if grid is None:
        return _unavailable_block("breach calendar grid not provided")
    arr = np.asarray(grid, dtype=float)
    if arr.ndim != 2 or arr.size == 0:
        return _unavailable_block("breach calendar must be a non-empty 2d grid")
    n_q, n_c = arr.shape
    q_labels = list(quarters) if quarters else [f"Q{i + 1}" for i in range(n_q)]
    c_labels = list(covenants) if covenants else [f"Cov{i + 1}" for i in range(n_c)]
    if len(q_labels) != n_q or len(c_labels) != n_c:
        return _unavailable_block("quarter/covenant labels must match grid shape")
    cells: list[dict[str, Any]] = []
    for i in range(n_q):
        for j in range(n_c):
            cells.append(
                {
                    "quarter": q_labels[i],
                    "covenant": c_labels[j],
                    "breach_probability": float(arr[i, j]),
                }
            )
    return {
        "unavailable": False,
        "quarters": q_labels,
        "covenants": c_labels,
        "grid": arr.tolist(),
        "cells": cells,
    }


def compute_stress_language_score(
    pillars: Mapping[str, float] | None,
) -> dict[str, Any]:
    if not pillars:
        return _unavailable_block("stress language pillars dict not provided")
    scores: dict[str, float] = {}
    for key in PILLAR_KEYS:
        raw = pillars.get(key)
        if raw is None:
            return _unavailable_block(f"missing pillar: {key}")
        scores[key] = float(np.clip(float(raw), 0.0, 100.0))
    composite = float(np.mean(list(scores.values())))
    return {
        "unavailable": False,
        "pillars": scores,
        "score": composite,
    }


def _has_index_credit_inputs(
    hy_oas_level: float | None,
    hy_oas_change_20d: float | None,
    cdx_hy: float | None,
    cdx_ig: float | None,
) -> bool:
    return any(x is not None for x in (hy_oas_level, hy_oas_change_20d, cdx_hy, cdx_ig))


class CreditTrajectoryEngine:
    """Disagreement and trajectory signals from CDX/HY OAS when issuer data is sparse."""

    def compute(
        self,
        as_of_date: pd.Timestamp | str,
        *,
        hy_oas_level: float | None = None,
        hy_oas_change_20d: float | None = None,
        cdx_ig: float | None = None,
        cdx_hy: float | None = None,
        vix: float | None = None,
        management_tone: float | None = None,
        pd_rows: Sequence[Mapping[str, Any]] | None = None,
        spread_bps: Sequence[float] | pd.Series | None = None,
        ltv: Sequence[float] | pd.Series | None = None,
        cliff_rows: Sequence[Mapping[str, Any]] | None = None,
        yield_shock_bps: float = 0.0,
        breach_grid: Sequence[Sequence[Any]] | None = None,
        breach_quarters: Sequence[str] | None = None,
        breach_covenants: Sequence[str] | None = None,
        stress_pillars: Mapping[str, float] | None = None,
    ) -> CreditTrajectoryOutput:
        as_of = pd.Timestamp(as_of_date)
        missing: list[str] = []

        if not _has_index_credit_inputs(hy_oas_level, hy_oas_change_20d, cdx_hy, cdx_ig):
            missing.append("index_credit_series")

        tone = compute_tone_vs_market_gap(
            management_tone=management_tone,
            hy_oas_level=hy_oas_level,
            hy_oas_change_20d=hy_oas_change_20d,
            vix=vix,
        )
        if tone.unavailable:
            missing.append("tone_vs_market_gap")

        pd_block = compute_pd_disagreement_points(pd_rows)
        if pd_block.get("unavailable"):
            missing.append("pd_disagreement")

        surface = compute_credit_surface_steepening(spread_bps, ltv)
        if surface.get("unavailable"):
            missing.append("credit_surface")

        cliff = compute_cliff_map_points(cliff_rows, yield_shock_bps=yield_shock_bps)
        if cliff.get("unavailable"):
            missing.append("cliff_map")

        breach = compute_breach_calendar_grid(
            breach_grid,
            quarters=breach_quarters,
            covenants=breach_covenants,
        )
        if breach.get("unavailable"):
            missing.append("breach_calendar")

        stress = compute_stress_language_score(stress_pillars)
        if stress.get("unavailable"):
            missing.append("stress_language")

        wholly_unavailable = "index_credit_series" in missing and tone.unavailable

        meta: dict[str, Any] = {}
        if cdx_ig is not None or cdx_hy is not None:
            meta["cdx_ig"] = cdx_ig
            meta["cdx_hy"] = cdx_hy
        if hy_oas_level is not None:
            meta["hy_oas_level_bps"] = hy_oas_level
        if hy_oas_change_20d is not None:
            meta["hy_oas_change_20d_bps"] = hy_oas_change_20d

        tone_out = tone.to_dict()
        tone_out.update(meta)

        return CreditTrajectoryOutput(
            effective_date=as_of,
            tone_vs_market_gap=tone_out,
            pd_disagreement=pd_block,
            credit_surface=surface,
            cliff_map=cliff,
            breach_calendar=breach,
            stress_language=stress,
            unavailable=wholly_unavailable,
            missing_inputs=missing,
        )
