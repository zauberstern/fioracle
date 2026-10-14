"""Group the engineered feature columns used by the fixed-income forecaster."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable, Mapping, Optional, Sequence

REGIMES: tuple[str, ...] = ("calm", "inflationary", "crisis")

GROUPS: tuple[dict, ...] = (
    {
        "id": "asset_returns",
        "bit": 0,
        "label": "Asset return features",
        "prefixes": ("avg_return_hl", "log_dd_hl", "sortino_hl"),
    },
    {
        "id": "vix",
        "bit": 1,
        "label": "Volatility (VIX)",
        "prefixes": ("vix_logdiff_ewma", "vix_level_norm"),
    },
    {
        "id": "geopolitical",
        "bit": 2,
        "label": "Geopolitical risk",
        "prefixes": ("gpr_logdiff_ewma", "gpr_level_norm"),
    },
    {
        "id": "credit",
        "bit": 3,
        "label": "Credit spreads",
        "prefixes": ("hy_oas_return_ewma", "hy_oas_level_norm"),
    },
    {
        "id": "rates_curve",
        "bit": 4,
        "label": "Yield curve",
        "prefixes": (
            "yield_2y_diff_ewma",
            "yield_slope_diff_ewma",
            "yield_slope_ewma",
        ),
    },
    {
        "id": "inflation",
        "bit": 5,
        "label": "Inflation",
        "prefixes": ("inflation_level", "inflation_change_ewma"),
    },
    {
        "id": "real_activity",
        "bit": 6,
        "label": "Growth and labor",
        "prefixes": (
            "gdp_growth_level",
            "gdp_growth_ewma",
            "unemployment_level",
            "unemployment_change_ewma",
        ),
    },
    {
        "id": "policy_liquidity",
        "bit": 7,
        "label": "Policy, fiscal, liquidity",
        "prefixes": (
            "epu_logdiff_ewma",
            "epu_level_norm",
            "debt_gdp_level",
            "debt_gdp_change_ewma",
            "m2_velocity_level",
            "m2_velocity_change_ewma",
            "stock_bond_corr_252d",
        ),
    },
)

CATEGORIES: tuple[dict, ...] = (
    {"id": "cash", "label": "Cash"},
    {"id": "government_bonds", "label": "Government bonds"},
    {"id": "investment_grade", "label": "Investment grade"},
    {"id": "high_yield", "label": "High yield"},
    {"id": "emerging_markets", "label": "Emerging markets"},
    {"id": "inflation_linked", "label": "Inflation-linked"},
    {
        "id": "safe_havens",
        "label": "Safe havens",
        "detail": "Gold and Swiss government bonds.",
    },
)

# Features-only sleeves. They must not appear as book weights.
EXCLUDED_SLEEVES: tuple[str, ...] = (
    "CHF_TOTAL_RETURN",
    "USD_SWAPTION_1Y_5Y_TOTAL_RETURN",
    "USD_SWAPTION_6M_5Y_TOTAL_RETURN",
    "USD_SWAPTION_1Y_10Y_TOTAL_RETURN",
    "US_INFLATION_SWAP_5Y_RETURN",
    "US_INFLATION_SWAP_1Y_RETURN",
    "US_INFLATION_SWAP_2Y_RETURN",
    "US_INFLATION_SWAP_10Y_RETURN",
)

BASELINE_MASK = 0xFF
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SUM_TOL = 1e-3


def mask_hex(mask: int) -> str:
    """Two lowercase hex digits, the scenario filename stem."""
    if not isinstance(mask, int) or isinstance(mask, bool) or not 0 <= mask <= 0xFF:
        raise ValueError(f"mask out of range: {mask!r}")
    return f"{mask:02x}"


def _bit(group_id: str) -> int:
    for group in GROUPS:
        if group["id"] == group_id:
            return int(group["bit"])
    raise KeyError(group_id)


def mask_from_on(group_ids: Iterable[str]) -> int:
    mask = 0
    for group_id in group_ids:
        mask |= 1 << _bit(group_id)
    return mask


def mask_from_off(group_ids: Iterable[str]) -> int:
    mask = BASELINE_MASK
    for group_id in group_ids:
        mask &= ~(1 << _bit(group_id))
    return mask


def _bare_column(name: str) -> str:
    text = str(name).strip()
    if text.startswith("macro_"):
        return text[len("macro_") :]
    return text


def classify_column(name: str) -> Optional[str]:
    """Map a feature column to one group id, or None if it is unknown.

    ``macro_`` is the prefix regimes.py adds when it builds the XGBoost matrix.
    Longer prefixes win so ``yield_slope_diff_ewma`` does not fall into
    ``yield_slope_ewma``.
    """
    bare = _bare_column(name)
    hits: list[tuple[int, str]] = []
    for group in GROUPS:
        for prefix in group["prefixes"]:
            if bare == prefix or bare.startswith(prefix):
                hits.append((len(prefix), group["id"]))
    if not hits:
        return None
    best_len = max(length for length, _gid in hits)
    best = {gid for length, gid in hits if length == best_len}
    if len(best) != 1:
        return None
    return next(iter(best))


def unmatched_columns(names: Sequence[str]) -> list[str]:
    return [name for name in names if classify_column(name) is None]


def contract_fingerprint() -> str:
    payload = {
        "bit_order": [group["id"] for group in GROUPS],
        "prefixes": {group["id"]: list(group["prefixes"]) for group in GROUPS},
        "categories": [cat["id"] for cat in CATEGORIES],
        "regimes": list(REGIMES),
        "excluded_sleeves": list(EXCLUDED_SLEEVES),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _presets() -> list[dict]:
    return [
        {
            "id": "all-on",
            "label": "Reset to all on",
            "mask": mask_hex(BASELINE_MASK),
        },
        {
            "id": "rates-credit",
            "label": "Rates and credit only",
            "mask": mask_hex(mask_from_on(("credit", "rates_curve"))),
        },
        {
            "id": "no-vix",
            "label": "No VIX",
            "mask": mask_hex(mask_from_off(("vix",))),
        },
        {
            "id": "macro-only",
            "label": "Macro only",
            "mask": mask_hex(mask_from_off(("asset_returns",))),
        },
    ]


def manifest_payload() -> dict:
    return {
        "schema_version": 1,
        "book": "fixed_income",
        "long_only": True,
        "rebalance_frequency": "weekly",
        "baseline_mask": mask_hex(BASELINE_MASK),
        "scenario_pattern": "scenarios/{mask}.json",
        "config_fingerprint": contract_fingerprint(),
        "regimes": list(REGIMES),
        "bit_order": [group["id"] for group in GROUPS],
        "groups": [
            {
                "id": group["id"],
                "bit": group["bit"],
                "label": group["label"],
                "prefixes": list(group["prefixes"]),
            }
            for group in GROUPS
        ],
        "categories": [dict(cat) for cat in CATEGORIES],
        "excluded_sleeves": list(EXCLUDED_SLEEVES),
        "presets": _presets(),
        "dates": [],
        "precompute": (
            "One walk-forward per mask from 00 through ff. Drop XGBoost columns "
            "whose group bit is off. Keep Jump Model labels fixed. Soft-mix the "
            "calm, inflationary, and crisis probabilities, then store long-only "
            "category weights on weekly rebalance dates."
        ),
    }


def _iso_dates(dates: object, label: str) -> list[str]:
    if not isinstance(dates, list):
        return [f"{label} must be a list"]
    errors = []
    for item in dates:
        if not isinstance(item, str) or not _DATE.match(item):
            errors.append(f"{label} has a non-ISO date: {item!r}")
    return errors


def validate_manifest(payload: Mapping) -> list[str]:
    expected = manifest_payload()
    errors: list[str] = []
    for key in (
        "schema_version",
        "book",
        "long_only",
        "rebalance_frequency",
        "baseline_mask",
        "scenario_pattern",
        "regimes",
        "bit_order",
        "groups",
        "categories",
        "excluded_sleeves",
        "presets",
    ):
        if payload.get(key) != expected[key]:
            errors.append(f"{key} does not match the feature atlas contract")
    if payload.get("config_fingerprint") != contract_fingerprint():
        errors.append("config_fingerprint does not match the feature atlas contract")
    errors.extend(_iso_dates(payload.get("dates"), "dates"))
    return errors


def _close(total: float, target: float = 1.0) -> bool:
    return abs(total - target) <= _SUM_TOL


def validate_scenario(doc: Mapping, manifest: Mapping) -> list[str]:
    errors: list[str] = []
    if "assets" in doc or "by_asset" in doc:
        errors.append("per-asset weights are not part of this atlas")
    mask = doc.get("mask")
    if not isinstance(mask, str) or not re.fullmatch(r"[0-9a-f]{2}", mask):
        errors.append(f"mask must be two lowercase hex digits, got {mask!r}")
    rows = doc.get("rows")
    if not isinstance(rows, list):
        return errors + ["rows must be a list"]
    allowed_dates = manifest.get("dates") or []
    date_set = set(allowed_dates) if isinstance(allowed_dates, list) else set()
    category_ids = [cat["id"] for cat in CATEGORIES]
    excluded = set(EXCLUDED_SLEEVES)
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {index} must be an object")
            continue
        date = row.get("date")
        if not isinstance(date, str) or not _DATE.match(date):
            errors.append(f"row {index} date is not ISO")
        elif date_set and date not in date_set:
            errors.append(f"row {index} date {date} is outside the manifest grid")
        probs = row.get("probs")
        if not isinstance(probs, dict):
            errors.append(f"row {index} probs must be an object")
        else:
            if set(probs) != set(REGIMES):
                errors.append(f"row {index} probs must be calm, inflationary, crisis")
            else:
                values = []
                for regime in REGIMES:
                    value = probs[regime]
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        errors.append(f"row {index} probs[{regime}] is not a number")
                        continue
                    if value < 0 or value > 1:
                        errors.append(f"row {index} probs[{regime}] is outside 0 to 1")
                    values.append(float(value))
                if len(values) == 3 and not _close(sum(values)):
                    errors.append(f"row {index} probs must sum to 1")
        weights = row.get("weights")
        if not isinstance(weights, dict):
            errors.append(f"row {index} weights must be an object")
            continue
        for key in weights:
            if key in excluded or key not in category_ids:
                errors.append(f"row {index} weights reject {key}")
        if set(weights) != set(category_ids):
            missing = [cid for cid in category_ids if cid not in weights]
            if missing:
                errors.append(f"row {index} weights missing {', '.join(missing)}")
            continue
        total = 0.0
        numeric = True
        for cid in category_ids:
            value = weights[cid]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"row {index} weights[{cid}] is not a number")
                numeric = False
                continue
            if value < -_SUM_TOL:
                errors.append(f"row {index} weights[{cid}] is short")
            total += float(value)
        if numeric and not _close(total):
            errors.append(f"row {index} weights must sum to 1")
    return errors
