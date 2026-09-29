"""Credit trajectory engine: available and gated unavailable paths."""

from __future__ import annotations

import pandas as pd
import pytest

from bubble_compass.brain.engines.credit_trajectory import (
    CreditTrajectoryEngine,
    compute_breach_calendar_grid,
    compute_cliff_map_points,
    compute_credit_surface_steepening,
    compute_pd_disagreement_points,
    compute_stress_language_score,
)
from bubble_compass.brain.engines.tone_vs_market import compute_tone_vs_market_gap


def test_tone_proxy_unavailable_without_vix_or_oas():
    out = compute_tone_vs_market_gap(vix=22.0)
    assert out.unavailable is True
    assert out.value is None


def test_tone_proxy_uses_vix_and_hy_oas_change():
    out = compute_tone_vs_market_gap(vix=30.0, hy_oas_change_20d=40.0)
    assert out.unavailable is False
    assert out.source == "vix_oas_proxy"
    assert out.value is not None
    assert -100.0 <= out.value <= 100.0
    assert out.value < 0


def test_pd_disagreement_unavailable_when_rows_missing():
    block = compute_pd_disagreement_points(None)
    assert block["unavailable"] is True


def test_pd_disagreement_emits_points():
    block = compute_pd_disagreement_points(
        [
            {
                "issuer": "ACME",
                "model_pd": 0.02,
                "market_pd": 0.05,
                "exposure": 1_000_000_000,
            }
        ]
    )
    assert block["unavailable"] is False
    assert block["points"][0]["gap_bps"] == pytest.approx(300.0)


def test_credit_surface_steepening_flag():
    spread = [200.0, 260.0, 340.0]
    ltv = [0.45, 0.55, 0.65]
    block = compute_credit_surface_steepening(spread, ltv, steepening_threshold=0.3)
    assert block["unavailable"] is False
    assert block["steepening_flag"] is True


def test_cliff_map_applies_yield_shock():
    base = compute_cliff_map_points(
        [{"issuer": "ACME", "months_to_wall": 18, "cost_to_ebitda": 4.0}],
        yield_shock_bps=0.0,
    )
    shocked = compute_cliff_map_points(
        [{"issuer": "ACME", "months_to_wall": 18, "cost_to_ebitda": 4.0}],
        yield_shock_bps=200.0,
    )
    assert base["unavailable"] is False
    assert shocked["points"][0]["cost_to_ebitda"] > base["points"][0]["cost_to_ebitda"]


def test_breach_calendar_grid_cells():
    grid = [[0.1, 0.8], [0.2, 0.3]]
    block = compute_breach_calendar_grid(
        grid,
        quarters=["2025Q1", "2025Q2"],
        covenants=["Leverage", "Interest"],
    )
    assert block["unavailable"] is False
    assert len(block["cells"]) == 4


def test_stress_language_requires_all_pillars():
    partial = compute_stress_language_score({"liquidity": 50.0})
    assert partial["unavailable"] is True
    full = compute_stress_language_score(
        {
            "liquidity": 40,
            "covenant": 60,
            "refinancing": 55,
            "downgrade": 70,
            "legal": 30,
        }
    )
    assert full["unavailable"] is False
    assert full["score"] == pytest.approx(51.0)


def test_engine_unavailable_when_no_market_series():
    out = CreditTrajectoryEngine().compute("2024-06-01")
    assert out.unavailable is True
    assert "index_credit_series" in out.missing_inputs
    assert out.tone_vs_market_gap["unavailable"] is True


def test_engine_partial_features_with_index_oas_and_vix():
    out = CreditTrajectoryEngine().compute(
        "2024-06-01",
        hy_oas_level=450.0,
        hy_oas_change_20d=25.0,
        vix=28.0,
        cdx_hy=110.0,
        stress_pillars={
            "liquidity": 10,
            "covenant": 20,
            "refinancing": 15,
            "downgrade": 25,
            "legal": 5,
        },
    )
    assert out.unavailable is False
    assert out.tone_vs_market_gap["unavailable"] is False
    assert out.stress_language["unavailable"] is False
    assert out.pd_disagreement["unavailable"] is True
    payload = out.to_dict()
    assert payload["effective_date"] == pd.Timestamp("2024-06-01").isoformat()
