"""Contract for the fixed-income feature groups."""

from __future__ import annotations

import re
from pathlib import Path

from src.core.feature_atlas import (
    BASELINE_MASK,
    CATEGORIES,
    EXCLUDED_SLEEVES,
    GROUPS,
    classify_column,
    contract_fingerprint,
    manifest_payload,
    mask_hex,
    mask_from_off,
    mask_from_on,
    unmatched_columns,
    validate_manifest,
    validate_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
FEATURES_PY = ROOT / "src" / "core" / "features.py"

BIT_ORDER = (
    "asset_returns",
    "vix",
    "geopolitical",
    "credit",
    "rates_curve",
    "inflation",
    "real_activity",
    "policy_liquidity",
)

FI_CATEGORIES = (
    "cash",
    "government_bonds",
    "investment_grade",
    "high_yield",
    "emerging_markets",
    "inflation_linked",
    "safe_havens",
)


def test_eight_groups_follow_bit_order():
    assert tuple(g["id"] for g in GROUPS) == BIT_ORDER
    assert [g["bit"] for g in GROUPS] == list(range(8))


def test_baseline_mask_is_all_groups_on():
    assert BASELINE_MASK == 0xFF
    assert mask_hex(BASELINE_MASK) == "ff"
    assert mask_hex(0) == "00"
    assert mask_from_off(()) == BASELINE_MASK
    assert mask_from_on(("credit", "rates_curve")) == (1 << 3) | (1 << 4)
    assert mask_from_off(("vix",)) == BASELINE_MASK ^ (1 << 1)
    assert mask_from_off(("asset_returns",)) == BASELINE_MASK ^ 1


def test_categories_are_fixed_income_only():
    assert tuple(c["id"] for c in CATEGORIES) == FI_CATEGORIES
    joined = " ".join(EXCLUDED_SLEEVES)
    assert "CHF_TOTAL_RETURN" in joined
    assert "USD_SWAPTION_1Y_5Y_TOTAL_RETURN" in joined
    assert "US_INFLATION_SWAP_5Y_RETURN" in joined
    for cat in CATEGORIES:
        assert "CHF" not in cat["id"]
        assert "SWAPTION" not in cat["id"]
        assert "FX" not in cat["id"]


def test_known_feature_columns_classify_and_unmatched_are_reported():
    assert classify_column("avg_return_hl21") == "asset_returns"
    assert classify_column("macro_vix_level_norm") == "vix"
    assert classify_column("macro_gpr_logdiff_ewma21") == "geopolitical"
    assert classify_column("hy_oas_level_norm") == "credit"
    assert classify_column("yield_slope_diff_ewma21") == "rates_curve"
    assert classify_column("macro_inflation_change_ewma21") == "inflation"
    assert classify_column("gdp_growth_ewma63") == "real_activity"
    assert classify_column("unemployment_level") == "real_activity"
    assert classify_column("macro_epu_level_norm") == "policy_liquidity"
    assert classify_column("debt_gdp_level") == "policy_liquidity"
    assert classify_column("m2_velocity_change_ewma63") == "policy_liquidity"
    assert classify_column("stock_bond_corr_252d") == "policy_liquidity"
    assert classify_column("not_a_feature") is None
    assert unmatched_columns(["macro_vix_level_norm", "mystery"]) == ["mystery"]


def test_every_engineered_feature_name_is_in_a_group():
    text = FEATURES_PY.read_text(encoding="utf-8")
    names = re.findall(r"(?:macro_)?features\[f?['\"]([^'\"]+)['\"]\]", text)
    assert names, "feature assignments missing from features.py"
    bare = []
    for name in names:
        stem = re.sub(r"\{[^}]+\}", "", name)
        bare.append(stem)
        assert classify_column(stem) is not None, stem
    assert unmatched_columns(bare) == []


def test_manifest_payload_and_committed_file():
    payload = manifest_payload()
    assert validate_manifest(payload) == []
    assert payload["baseline_mask"] == "ff"
    assert payload["rebalance_frequency"] == "weekly"
    assert payload["book"] == "fixed_income"
    assert payload["long_only"] is True
    assert payload["regimes"] == ["calm", "inflationary", "crisis"]
    assert payload["config_fingerprint"] == contract_fingerprint()
    assert payload["dates"] == []
    on_ids = {p["id"]: p for p in payload["presets"]}
    assert on_ids["rates-credit"]["mask"] == "18"
    assert on_ids["no-vix"]["mask"] == "fd"
    assert on_ids["macro-only"]["mask"] == "fe"


def test_scenario_accepts_book_mean_probs_and_category_weights():
    manifest = manifest_payload()
    manifest["dates"] = ["2018-01-05", "2018-01-12"]
    weights = {c["id"]: 0.0 for c in CATEGORIES}
    weights["government_bonds"] = 0.6
    weights["investment_grade"] = 0.25
    weights["safe_havens"] = 0.15
    doc = {
        "mask": "ff",
        "rows": [
            {
                "date": "2018-01-05",
                "probs": {"calm": 0.5, "inflationary": 0.3, "crisis": 0.2},
                "weights": weights,
            }
        ],
    }
    assert validate_scenario(doc, manifest) == []


def test_scenario_rejects_fx_sleeve_and_bad_probs():
    manifest = manifest_payload()
    manifest["dates"] = ["2018-01-05"]
    weights = {c["id"]: 0.0 for c in CATEGORIES}
    weights["cash"] = 1.0
    weights["CHF_TOTAL_RETURN"] = 0.2
    doc = {
        "mask": "ff",
        "rows": [
            {
                "date": "2018-01-05",
                "probs": {"calm": 0.5, "inflationary": 0.5, "crisis": 0.5},
                "weights": weights,
            }
        ],
    }
    errors = validate_scenario(doc, manifest)
    assert any("CHF_TOTAL_RETURN" in err for err in errors)
    assert any("probs" in err for err in errors)


def test_scenario_rejects_per_asset_weights():
    manifest = manifest_payload()
    manifest["dates"] = ["2018-01-05"]
    weights = {c["id"]: 0.0 for c in CATEGORIES}
    weights["cash"] = 1.0
    doc = {
        "mask": "ff",
        "assets": {"GOLD_TOTAL_RETURN": 0.1},
        "rows": [
            {
                "date": "2018-01-05",
                "probs": {"calm": 1.0, "inflationary": 0.0, "crisis": 0.0},
                "weights": weights,
            }
        ],
    }
    errors = validate_scenario(doc, manifest)
    assert any("per-asset" in err for err in errors)


def test_feature_page_contract():
    assert not (DOCS / "features").exists()
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert 'href="features/"' not in index
