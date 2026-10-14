"""Build the sandbox replay bundle from the saved max_cap_tree book.

The browser only multiplies. Dates, costs, and wealth live here.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TREE_SLEEVES = {
    "BBG_US_CORPORATE",
    "BBG_US_HIGH_YIELD",
    "BBG_US_TREASURY",
    "GOLD",
    "US_10Y_GOV_BOND",
    "US_BOND_AGG",
}
MACRO_PICKS = (
    "vix_level_norm",
    "hy_oas_level_norm",
    "unemployment_level",
    "inflation_level",
)
BENCH_LINES = {
    "sixty_forty": "60_40",
    "agg_buy_hold": "agg_buy_hold",
    "true_ew_buy_hold": "true_ew_buy_hold",
    "barbell": "barbell",
    "diversified_core": "diversified_core",
    "inv_vol": "inv_vol_risk_parity",
    "unconditional_minvar": "unconditional_minvar",
    "unconditional_mvo": "unconditional_mvo",
    "cash": "cash",
}


def plain_date(iso: str) -> str:
    text = str(iso)[:10]
    year, month, day = text.split("-")
    return f"{int(day)} {MONTHS[int(month) - 1]} {year}"


def cost_for_asset(name: str, table: dict, default: float) -> float:
    folded = str(name).upper()
    best = None
    best_len = 0
    for pattern, cost in table.items():
        token = str(pattern).upper()
        if token in folded and len(token) > best_len:
            best = float(cost)
            best_len = len(token)
    return float(default if best is None else best)


def to_bps(weights) -> list[int]:
    raw = np.asarray(weights, dtype=float) * 10000.0
    raw = np.where(np.isfinite(raw), raw, 0.0)
    floors = np.floor(raw + 1e-9).astype(int)
    leftover = int(10000 - int(floors.sum()))
    order = np.argsort(-(raw - floors))
    for step in range(max(0, leftover)):
        floors[order[step % len(floors)]] += 1
    if leftover < 0:
        order = np.argsort(floors)
        for step in range(-leftover):
            take = order[-(step % len(floors)) - 1]
            if floors[take] > 0:
                floors[take] -= 1
    return [int(v) for v in floors]


def format_value(value: float) -> str:
    number = float(value)
    magnitude = abs(number)
    if magnitude >= 100:
        return str(int(round(number)))
    if magnitude >= 10:
        return f"{number:.1f}"
    if magnitude < 5e-4:
        return "0"
    return f"{number:.4f}".rstrip("0").rstrip(".")


def choice_label(before, after, ids, label_of) -> str:
    delta = np.asarray(after, dtype=float) - np.asarray(before, dtype=float)
    order = np.argsort(-np.abs(delta))
    parts = []
    for pos in order[:3]:
        change = float(delta[pos])
        if abs(change) < 5e-5:
            continue
        verb = "Add" if change > 0 else "Cut"
        parts.append(f"{verb} {label_of(ids[pos])} {int(round(abs(change) * 10000))} bp")
    return ", ".join(parts) if parts else "Hold these weights"


def _long_only(vector: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(vector, dtype=float), 0.0, None)
    total = float(clipped.sum())
    if total <= 1e-12:
        out = np.zeros_like(clipped)
        out[-1] = 1.0
        return out
    return clipped / total


def _distinct(vector, kept, tol=1e-4) -> bool:
    return all(np.max(np.abs(vector - other)) >= tol for other in kept)


def _group_mask(ids, kind: str) -> np.ndarray:
    mask = []
    for name in ids:
        if name == "cash_allocation":
            mask.append(False)
            continue
        if kind == "treasury":
            mask.append(
                name in {"US_10Y_GOV_BOND", "BBG_US_TREASURY"}
                or (name.startswith("ISHARES_") and "TREASURY" in name)
            )
        else:
            mask.append(name in {"BBG_US_CORPORATE", "BBG_US_HIGH_YIELD"})
    return np.array(mask, dtype=bool)


def _bucket(ids, book, kind: str) -> np.ndarray | None:
    mask = _group_mask(ids, kind)
    if not mask.any():
        return None
    out = np.zeros(len(ids), dtype=float)
    risky = float(np.clip(book[:-1], 0, None).sum()) if ids[-1] == "cash_allocation" else float(np.clip(book, 0, None).sum())
    base = np.clip(book[mask], 0, None)
    if base.sum() <= 1e-12:
        base = np.ones(int(mask.sum()))
    out[mask] = base / base.sum() * (risky if risky > 1e-8 else 0.5)
    if ids[-1] == "cash_allocation":
        out[-1] = max(0.0, 1.0 - float(out[:-1].sum()))
    return _long_only(out)


def _flip(ids, previous, book) -> np.ndarray | None:
    delta = book - previous
    pos = int(np.argmax(delta))
    neg = int(np.argmin(delta))
    if pos == neg or delta[pos] <= 1e-8 or delta[neg] >= -1e-8:
        return None
    flipped = book.copy()
    flipped[pos], flipped[neg] = flipped[neg], flipped[pos]
    return _long_only(flipped)


def _shift_to_cash(book, bps: int) -> np.ndarray:
    out = book.copy()
    pos = int(np.argmax(out[:-1])) if len(out) > 1 else 0
    move = min(bps / 10000.0, float(out[pos]))
    out[pos] -= move
    out[-1] += move
    return _long_only(out)


def choice_vectors(ids, previous, book, mv, ew) -> list[np.ndarray]:
    book = _long_only(np.asarray(book, dtype=float))
    previous = _long_only(np.asarray(previous, dtype=float))
    mv = _long_only(np.asarray(mv, dtype=float))
    ew = _long_only(np.asarray(ew, dtype=float))
    cash = np.zeros(len(ids), dtype=float)
    cash[-1] = 1.0
    pool = [book, mv, ew, previous, cash, _flip(ids, previous, book), _bucket(ids, book, "treasury"), _bucket(ids, book, "credit")]
    for shift in (500, 1000, 1500, 2000, 2500):
        pool.append(_shift_to_cash(book, shift))
    cash_at = ids.index("cash_allocation") if "cash_allocation" in ids else len(ids) - 1
    for name in ("US_10Y_GOV_BOND", "BBG_US_TREASURY", "BBG_US_CORPORATE", "BBG_US_HIGH_YIELD", "GOLD", "US_CASH"):
        if name not in ids:
            continue
        single = np.zeros(len(ids), dtype=float)
        single[ids.index(name)] = 0.25
        single[cash_at] = 0.75
        pool.append(single)
    kept: list[np.ndarray] = []
    for vector in pool:
        if vector is None:
            continue
        vector = _long_only(vector)
        if _distinct(vector, kept):
            kept.append(vector)
        if len(kept) == 8:
            break
    if len(kept) < 8:
        raise RuntimeError(f"Only {len(kept)} distinct choices")
    return kept


def menu_choices(ids, previous, book, mv, ew) -> list[tuple[str, np.ndarray]]:
    """Eight distinct policies, tagged before any display shuffle."""
    book = _long_only(np.asarray(book, dtype=float))
    previous = _long_only(np.asarray(previous, dtype=float))
    mv = _long_only(np.asarray(mv, dtype=float))
    ew = _long_only(np.asarray(ew, dtype=float))
    cash = np.zeros(len(ids), dtype=float)
    cash[-1] = 1.0
    pool: list[tuple[str, np.ndarray | None]] = [
        ("book", book),
        ("mv", mv),
        ("ew", ew),
        ("previous", previous),
        ("cash", cash),
        ("flip", _flip(ids, previous, book)),
        ("treasury", _bucket(ids, book, "treasury")),
        ("credit", _bucket(ids, book, "credit")),
    ]
    for shift in (500, 1000, 1500, 2000, 2500):
        pool.append((f"shift{shift}", _shift_to_cash(book, shift)))
    cash_at = ids.index("cash_allocation") if "cash_allocation" in ids else len(ids) - 1
    for name in ("US_10Y_GOV_BOND", "BBG_US_TREASURY", "BBG_US_CORPORATE", "BBG_US_HIGH_YIELD", "GOLD", "US_CASH"):
        if name not in ids:
            continue
        single = np.zeros(len(ids), dtype=float)
        single[ids.index(name)] = 0.25
        single[cash_at] = 0.75
        pool.append((f"sleeve:{name}", single))
    kept: list[tuple[str, np.ndarray]] = []
    seen: list[np.ndarray] = []
    for policy, vector in pool:
        if vector is None:
            continue
        vector = _long_only(vector)
        if not _distinct(vector, seen):
            continue
        kept.append((policy, vector))
        seen.append(vector)
        if len(kept) == 8:
            break
    if len(kept) < 8:
        raise RuntimeError(f"Only {len(kept)} distinct choices")
    return kept


def _family(name: str, label: str) -> str:
    if name == "cash_allocation" or "Uninvested" in label:
        return "idle"
    if name == "US_CASH" or label == "Cash":
        return "cash"
    if name == "GOLD" or label == "Gold":
        return "gold"
    if name == "BBG_US_HIGH_YIELD" or label == "US HY":
        return "hy"
    if name == "BBG_US_CORPORATE" or label in {"US IG", "US AAA", "US BBB"}:
        return "ig"
    if name == "US_10Y_GOV_BOND" or label == "US10Y" or "20Y" in label or "7-10" in label:
        return "long"
    if name in {"BBG_US_TREASURY", "ISHARES_1_3Y_TREASURY"} or label in {"UST", "UST 1-3Y"}:
        return "short"
    if name in {"US_BOND_AGG", "BBG_GLOBAL_AGG", "BBG_EM_USD_AGG", "VANGUARD_TOTAL_BOND"} or "Agg" in label:
        return "agg"
    return label


def _pp(change: float) -> str:
    magnitude = abs(change) * 100.0
    if magnitude >= 1:
        return str(int(round(magnitude)))
    return f"{magnitude:.1f}"


DESK_NAMES = {
    "US_CASH": "Treasury bills",
    "US_10Y_GOV_BOND": "the 10-year Treasury",
    "ISHARES_20Y_TREASURY": "Treasuries beyond 20 years",
    "ISHARES_7_10Y_TREASURY": "Treasuries from 7 to 10 years",
    "ISHARES_1_3Y_TREASURY": "Treasuries from 1 to 3 years",
    "BBG_US_TREASURY": "the Treasury index",
    "US_BOND_AGG": "the US aggregate bond",
    "VANGUARD_TOTAL_BOND": "the total bond fund",
    "BBG_US_CORPORATE": "investment grade credit",
    "BBG_GLOBAL_AGG": "the global aggregate bond",
    "BBG_US_HIGH_YIELD": "high yield credit",
    "BBG_EM_USD_AGG": "emerging market bonds",
    "US_TIPS_0_5": "short inflation-linked Treasuries",
    "GLOBAL_ILB_0_5": "short global inflation-linked bonds",
    "ISHARES_SWISS_GOV_7_15": "Swiss government bonds",
    "GOLD": "gold",
    "cash_allocation": "uninvested cash",
}

HEADLINE_NOUN = {
    "US_CASH": "Treasury bills",
    "US_10Y_GOV_BOND": "the 10-year",
    "ISHARES_20Y_TREASURY": "long Treasuries",
    "ISHARES_7_10Y_TREASURY": "intermediate Treasuries",
    "ISHARES_1_3Y_TREASURY": "short Treasuries",
    "BBG_US_TREASURY": "the Treasury index",
    "US_BOND_AGG": "the US aggregate",
    "VANGUARD_TOTAL_BOND": "the total bond fund",
    "BBG_US_CORPORATE": "investment grade credit",
    "BBG_GLOBAL_AGG": "the global aggregate",
    "BBG_US_HIGH_YIELD": "high yield credit",
    "BBG_EM_USD_AGG": "emerging market bonds",
    "US_TIPS_0_5": "inflation-linked Treasuries",
    "GLOBAL_ILB_0_5": "global inflation-linked bonds",
    "ISHARES_SWISS_GOV_7_15": "Swiss government bonds",
    "GOLD": "gold",
    "cash_allocation": "uninvested cash",
}


def desk_name(name: str) -> str:
    return DESK_NAMES.get(name, name)


def choice_lines(before, after, ids, label_of) -> tuple[str, str]:
    before_bps = to_bps(np.asarray(before, dtype=float))
    after_bps = to_bps(np.asarray(after, dtype=float))
    if before_bps == after_bps:
        return "Hold these weights", ""
    delta = [after_bps[i] - before_bps[i] for i in range(len(ids))]
    order = sorted(range(len(ids)), key=lambda i: abs(delta[i]), reverse=True)
    parts = []
    for pos in order:
        if abs(delta[pos]) < 50:
            continue
        new_pp = _pp(after_bps[pos] / 10000.0)
        change = _pp(abs(delta[pos]) / 10000.0)
        noun = desk_name(ids[pos])
        verb = "go" if noun.endswith("s") else "goes"
        direction = "up" if delta[pos] > 0 else "down"
        parts.append(f"{noun} {verb} {direction} {change} percentage points, to {new_pp}")
        if len(parts) == 2:
            break
    lead = order[0]
    noun = HEADLINE_NOUN.get(ids[lead], desk_name(ids[lead]))
    if delta[lead] > 0 and ids[lead] in {"US_CASH", "cash_allocation"}:
        verb = "Raise"
    elif delta[lead] > 0:
        verb = "Add"
    else:
        verb = "Cut"
    headline = f"{verb} {noun}"
    opposite = None
    for pos in order[1:]:
        if delta[pos] * delta[lead] < 0:
            opposite = pos
            break
    if opposite is not None:
        source = HEADLINE_NOUN.get(ids[opposite], desk_name(ids[opposite]))
        if source.lower() not in headline.lower():
            if delta[lead] > 0 and delta[opposite] < 0:
                link = "cut" if ids[lead] in {"US_CASH", "cash_allocation"} else "fund from"
                headline = f"{headline}, {link} {source}"
            elif delta[lead] < 0 and delta[opposite] > 0:
                headline = f"{headline}, add {source}"
    detail = parts[0] if len(parts) == 1 else ""
    if len(parts) == 2:
        detail = f"{parts[0]}, and {parts[1]}"
    return headline, detail


PLAIN_FEATURE = {
    "avg_return_hl5": "the 5-day excess return",
    "avg_return_hl10": "the 10-day excess return",
    "avg_return_hl21": "the 21-day excess return",
    "macro_yield_slope_ewma10": "the 10-year minus 2-year slope",
    "macro_unemployment_level": "the unemployment rate",
    "macro_unemployment_change_ewma21": "the change in unemployment",
    "macro_gpr_level_norm": "geopolitical risk",
    "macro_inflation_level": "the inflation rate",
    "macro_inflation_change_ewma21": "the change in inflation",
    "macro_hy_oas_level_norm": "the high-yield credit spread",
    "macro_hy_oas_return_ewma21": "the change in the high-yield credit spread",
    "macro_stock_bond_corr_252d": "the stock and bond correlation",
}


def _prob(value: float) -> str:
    return f"{float(value):.3f}"


def explain_miss(book_bps, choice_bps, ids, evidence, label_of) -> str:
    """Why FIOracle differs from this choice. Empty when the vectors match."""
    if [int(v) for v in book_bps] == [int(v) for v in choice_bps]:
        return ""
    gaps = []
    for pos, name in enumerate(ids):
        delta = int(choice_bps[pos]) - int(book_bps[pos])
        if abs(delta) >= 50:
            gaps.append((abs(delta), delta, name))
    gaps.sort(reverse=True)
    gap_lines = ["This choice does not match FIOracle."]
    for _size, delta, name in gaps[:2]:
        points = _pp(abs(delta) / 10000.0)
        noun = label_of(name)
        if delta > 0:
            gap_lines.append(f"You hold {points} percentage points more in {noun}.")
        else:
            gap_lines.append(f"FIOracle holds {points} percentage points more in {noun}.")
    probs = {row["id"]: row for row in evidence.get("probs") or []}
    ranked = {row["id"]: row for row in evidence.get("importance") or []}
    inputs = {row["id"]: row["text"] for row in evidence.get("inputs") or []}
    cited: list[str] = []
    for _size, _delta, name in gaps:
        if name in probs and name not in cited:
            cited.append(name)
        if len(cited) == 2:
            break
    feature_sleeve = evidence.get("feature_sleeve")
    if not cited and feature_sleeve in probs:
        cited.append(feature_sleeve)
    date = evidence.get("date") or "this date"
    chance = []
    ranked_lines = []
    for name in cited:
        row = probs[name]
        noun = row.get("label") or label_of(name)
        chance.append(
            f"On {date} the saved booster for {noun} assigned calm {_prob(row['calm'])}, "
            f"inflationary {_prob(row['inflationary'])}, and crisis {_prob(row['crisis'])}."
        )
        rank = ranked.get(name)
        if rank and float(rank.get("importance") or 0) > 0:
            plain = rank.get("plain") or PLAIN_FEATURE.get(rank.get("feature", ""), rank.get("feature", "the input"))
            ranked_lines.append(
                f"The test diagnostic for the {noun} booster, over the whole test window, "
                f"ranks {plain} first at {_prob(rank['importance'])}."
            )
            recorded = inputs.get(rank.get("feature", ""))
            if recorded:
                ranked_lines.append(f"Recorded that day, {recorded}.")
    if chance:
        chance.append("The minimum-variance book used these probabilities.")
    ranked_lines.append("The scaler was not saved, so the page does not replay the leaf.")
    paragraphs = [" ".join(gap_lines)]
    if chance:
        paragraphs.append(" ".join(chance))
    paragraphs.append(" ".join(ranked_lines))
    return "\n\n".join(paragraphs)


def _question_evidence(day, feature_sleeve, features, probs, diagnostics, sleeves, label_of) -> dict:
    stamp = str(pd.Timestamp(day).date())
    known = set(sleeves) | {"US_CASH"}
    prob_rows = []
    for asset_name, blob in probs.items():
        if asset_name not in known:
            continue
        index = [str(item)[:10] for item in blob.get("index") or []]
        if stamp not in index:
            continue
        values = blob["data"][index.index(stamp)]
        if len(values) < 3:
            continue
        prob_rows.append(
            {
                "id": asset_name,
                "label": label_of(asset_name),
                "calm": round(float(values[0]), 6),
                "inflationary": round(float(values[1]), 6),
                "crisis": round(float(values[2]), 6),
            }
        )
    importance = []
    for asset_name, blob in diagnostics.items():
        ranks = ((blob.get("xgb_diagnostics") or {}).get("feature_importance") or [])
        if not ranks:
            continue
        top = ranks[0]
        weight = float(top.get("importance") or 0)
        if weight <= 0:
            continue
        fid = str(top.get("feature") or "")
        importance.append(
            {
                "id": asset_name,
                "feature": fid,
                "plain": PLAIN_FEATURE.get(fid, fid),
                "importance": round(weight, 6),
            }
        )
    return {
        "date": plain_date(stamp),
        "feature_sleeve": feature_sleeve,
        "probs": prob_rows,
        "importance": importance,
        "inputs": [{"id": item["id"], "text": feature_clause(item)} for item in features],
    }


ASSET_FEATURE_IDS = (
    "avg_return_hl5",
    "avg_return_hl10",
    "avg_return_hl21",
    "log_dd_hl5",
    "log_dd_hl21",
    "sortino_hl5",
    "sortino_hl10",
    "sortino_hl21",
)
MACRO_FEATURE_IDS = (
    "vix_logdiff_ewma63",
    "vix_level_norm",
    "gpr_logdiff_ewma21",
    "gpr_level_norm",
    "hy_oas_return_ewma21",
    "hy_oas_level_norm",
    "unemployment_level",
    "unemployment_change_ewma21",
    "inflation_level",
    "inflation_change_ewma21",
    "yield_2y_diff_ewma21",
    "yield_slope_ewma10",
    "yield_slope_diff_ewma21",
    "stock_bond_corr_252d",
)


def _sig(value: float) -> str:
    number = float(value)
    if number != 0 and abs(number) < 1e-3:
        return f"{number:.6f}".rstrip("0").rstrip(".")
    return f"{number:.3g}"


def _z(value: float) -> str:
    side = "above" if value >= 0 else "below"
    return f"{format_value(abs(value))} standard deviations {side} its history"


def _rate_percent(value: float) -> str:
    return f"{value * 100.0:.1f} percent"


def feature_clause(feature: dict) -> str:
    fid = feature.get("id") or ""
    value = float(feature["value"])
    if fid.startswith("avg_return_hl"):
        days = fid.replace("avg_return_hl", "")
        return f"{days}-day excess return {_sig(value * 100.0)} percent per day"
    if fid.startswith("log_dd_hl"):
        days = fid.replace("log_dd_hl", "")
        return f"{days}-day downside {_sig(value)}"
    if fid.startswith("sortino_hl"):
        days = fid.replace("sortino_hl", "")
        return f"{days}-day Sortino {_sig(value)}"
    if fid == "macro_vix_level_norm":
        return f"smoothed volatility index is {_z(value)}"
    if fid == "macro_vix_logdiff_ewma63":
        return f"volatility index log change {_sig(value)}"
    if fid == "macro_hy_oas_level_norm":
        return f"high-yield credit spread is {_z(value)}"
    if fid == "macro_hy_oas_return_ewma21":
        return f"high-yield credit spread change {_sig(value)}"
    if fid == "macro_gpr_level_norm":
        return f"geopolitical risk is {_z(value)}"
    if fid == "macro_gpr_logdiff_ewma21":
        return f"geopolitical risk log change {_sig(value)}"
    if fid == "macro_unemployment_level":
        return f"unemployment is {_rate_percent(value)}"
    if fid == "macro_unemployment_change_ewma21":
        return f"unemployment change {_sig(value)} percentage points"
    if fid == "macro_inflation_level":
        return f"inflation is {_rate_percent(value)}"
    if fid == "macro_inflation_change_ewma21":
        return f"inflation change {_sig(value)} percentage points"
    if fid == "macro_yield_2y_diff_ewma21":
        return f"2-year yield change {_sig(value)} percentage points"
    if fid == "macro_yield_slope_ewma10":
        return f"10-year minus 2-year slope {_sig(value)} percentage points"
    if fid == "macro_yield_slope_diff_ewma21":
        return f"slope change {_sig(value)} percentage points"
    if fid == "macro_stock_bond_corr_252d":
        return f"stock and bond correlation {_sig(value)}"
    return f"{feature.get('label', fid)} is {format_value(value)}"


def _have(features: list) -> dict[str, float]:
    return {item["id"]: float(item["value"]) for item in features if np.isfinite(item["value"])}


def _joined(values: list[str]) -> str:
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + ", and " + values[-1]


def _pair(left: str, right: str) -> str:
    if left and right:
        return f"{left} {right}"
    return left or right


def format_prompt(sleeve: str, date: str, features: list, regime: str | None, cash_moved: bool = False) -> str:
    have = _have(features)
    paragraphs = []
    if cash_moved:
        paragraphs.append(
            f"On {plain_date(date)}, uninvested cash had the largest change in the weights. "
            f"The figures below are the inputs for {sleeve}."
        )
    else:
        paragraphs.append(f"On {plain_date(date)}, these were the inputs for {sleeve}.")
    returns = []
    for fid, days in (("avg_return_hl5", "5"), ("avg_return_hl10", "10"), ("avg_return_hl21", "21")):
        if fid in have:
            returns.append(f"{_sig(have[fid] * 100.0)} percent per day over {days} days")
    if returns:
        paragraphs.append("Excess return over cash is " + _joined(returns) + ".")
    downside = []
    for fid, days in (("log_dd_hl5", "5"), ("log_dd_hl21", "21")):
        if fid in have:
            downside.append(f"the log of {days}-day downside deviation is {_sig(have[fid])}")
    if downside:
        text = _joined(downside)
        paragraphs.append(text[:1].upper() + text[1:] + ".")
    sortino = []
    for fid, days in (("sortino_hl5", "5"), ("sortino_hl10", "10"), ("sortino_hl21", "21")):
        if fid in have:
            sortino.append(f"{_sig(have[fid])} at {days} days")
    if sortino:
        paragraphs.append(
            "Sortino, the average excess return over that downside, is " + _joined(sortino) + "."
        )
    vol_change = (
        "Smoothed over 63 days, the daily log change in the volatility index is "
        + _sig(have["macro_vix_logdiff_ewma63"])
        + "."
        if "macro_vix_logdiff_ewma63" in have
        else ""
    )
    vol_level = (
        "The smoothed index is " + _z(have["macro_vix_level_norm"]) + "."
        if "macro_vix_level_norm" in have
        else ""
    )
    if vol_change or vol_level:
        paragraphs.append(_pair(vol_change, vol_level))
    gpr_change = (
        "The log change in geopolitical risk is " + _sig(have["macro_gpr_logdiff_ewma21"]) + "."
        if "macro_gpr_logdiff_ewma21" in have
        else ""
    )
    gpr_level = (
        "Geopolitical risk is " + _z(have["macro_gpr_level_norm"]) + "."
        if "macro_gpr_level_norm" in have
        else ""
    )
    if gpr_change or gpr_level:
        paragraphs.append(_pair(gpr_change, gpr_level))
    credit_change = (
        "Smoothed over 21 days, the daily percent change in the high-yield credit spread is "
        + _sig(have["macro_hy_oas_return_ewma21"])
        + "."
        if "macro_hy_oas_return_ewma21" in have
        else ""
    )
    credit_level = (
        "The high-yield credit spread is " + _z(have["macro_hy_oas_level_norm"]) + "."
        if "macro_hy_oas_level_norm" in have
        else ""
    )
    if credit_change or credit_level:
        paragraphs.append(_pair(credit_change, credit_level))
    labor_level = (
        "The unemployment rate is " + _rate_percent(have["macro_unemployment_level"]) + "."
        if "macro_unemployment_level" in have
        else ""
    )
    labor_change = (
        "Smoothed over 21 days, its daily change is "
        + _sig(have["macro_unemployment_change_ewma21"])
        + " percentage points."
        if "macro_unemployment_change_ewma21" in have
        else ""
    )
    if labor_level or labor_change:
        paragraphs.append(_pair(labor_level, labor_change))
    infl_level = (
        "The inflation rate is " + _rate_percent(have["macro_inflation_level"]) + "."
        if "macro_inflation_level" in have
        else ""
    )
    infl_change = (
        "Smoothed over 21 days, its daily change is "
        + _sig(have["macro_inflation_change_ewma21"])
        + " percentage points."
        if "macro_inflation_change_ewma21" in have
        else ""
    )
    if infl_level or infl_change:
        paragraphs.append(_pair(infl_level, infl_change))
    curve = []
    if "macro_yield_2y_diff_ewma21" in have:
        curve.append(
            "the 21-day smooth of the daily change in the 2-year yield is "
            + _sig(have["macro_yield_2y_diff_ewma21"])
            + " percentage points"
        )
    if "macro_yield_slope_ewma10" in have:
        curve.append(
            "the 10-year minus 2-year slope is " + _sig(have["macro_yield_slope_ewma10"]) + " percentage points"
        )
    if "macro_yield_slope_diff_ewma21" in have:
        curve.append(
            "the 21-day smooth of the daily change in that slope is "
            + _sig(have["macro_yield_slope_diff_ewma21"])
            + " percentage points"
        )
    if curve:
        text = _joined(curve)
        paragraphs.append(text[:1].upper() + text[1:] + ".")
    if "macro_stock_bond_corr_252d" in have:
        paragraphs.append(
            "The 252-day correlation between stocks and bonds is "
            + _sig(have["macro_stock_bond_corr_252d"])
            + "."
        )
    if regime:
        paragraphs.append(f"The regime label is {regime}.")
    paragraphs.append("Which weights do you hold?")
    return "\n\n".join(paragraphs)


def _policy_row(policy, ids, book, prev, mv, ew, live):
    """Return a basis-point row, or None when that policy cannot be built."""
    book = [int(v) for v in book]
    width = len(ids)

    def dead(row) -> bool:
        if not live:
            return False
        for pos, flag in enumerate(live):
            if pos < width - 1 and row[pos] > 0 and not flag:
                return True
        return False

    if policy == "book":
        return None if dead(book) else book
    if policy == "mv":
        if mv is None:
            return None
        row = [int(v) for v in mv]
        return None if dead(row) else row
    if policy == "ew":
        if ew is None:
            return None
        row = [int(v) for v in ew]
        return None if dead(row) else row
    if policy == "previous":
        return [int(v) for v in prev] if prev is not None else None
    if policy == "cash":
        row = [0] * width
        row[-1] = 10000
        return row
    if policy == "flip":
        delta = np.asarray(book, dtype=float) - np.asarray(prev, dtype=float)
        pos = int(np.argmax(delta))
        neg = int(np.argmin(delta))
        if pos == neg or delta[pos] <= 0 or delta[neg] >= 0:
            return None
        row = book[:]
        row[pos], row[neg] = row[neg], row[pos]
        return to_bps(np.asarray(row, dtype=float) / 10000.0)
    if policy in {"treasury", "credit"}:
        mask = _group_mask(ids, policy)
        if int(np.asarray(book)[mask].sum()) < 1:
            return None
        vector = _bucket(ids, np.asarray(book, dtype=float) / 10000.0, policy)
        if vector is None:
            return None
        return to_bps(vector)
    if policy.startswith("shift"):
        vector = _shift_to_cash(np.asarray(book, dtype=float) / 10000.0, int(policy.replace("shift", "") or "0"))
        return to_bps(vector)
    if policy.startswith("sleeve:"):
        name = policy.split(":", 1)[1]
        if name not in ids:
            return None
        pos = ids.index(name)
        if live and pos < len(live) and not live[pos]:
            return None
        row = [0] * width
        row[pos] = 2500
        row[-1] = 7500
        return row
    return None


def _zero_dead(row: list[int] | None, live) -> list[int] | None:
    if row is None or not live:
        return row
    cleaned = [int(v) for v in row]
    changed = False
    for pos, flag in enumerate(live):
        if pos < len(cleaned) - 1 and not flag and cleaned[pos] != 0:
            cleaned[pos] = 0
            changed = True
    if not changed:
        return cleaned
    total = sum(cleaned)
    if total <= 0:
        cleaned = [0] * len(cleaned)
        cleaned[-1] = 10000
        return cleaned
    return to_bps(np.asarray(cleaned, dtype=float) / total)


def _mix_bps(style: dict, built: dict) -> list[int] | None:
    keys = [key for key, weight in style.items() if weight > 0 and built.get(key)]
    if not keys:
        return None
    total = sum(style[key] for key in keys)
    width = len(next(iter(built.values())))
    acc = np.zeros(width, dtype=float)
    for key in keys:
        acc += (style[key] / total) * np.asarray(built[key], dtype=float)
    return to_bps(acc / 10000.0)


def style_fill(ids, book_rows, mv_rows, ew_rows, live_rows, question_indexes, answers):
    """Weights through the latest answer. None after that. Cash before the first answer."""
    count = len(book_rows)
    width = len(ids)
    cash = [0] * (width - 1) + [10000]
    answered = sorted(day for day in question_indexes if day in answers)
    if not answered:
        return [None] * count
    first = answered[0]
    book_end = answered[-1]
    out: list = [None] * count
    for day in range(first):
        out[day] = cash[:]
    for day in range(first, book_end + 1):
        if day in answers:
            out[day] = [int(v) for v in answers[day]["bps"]]
            continue
        prior = [q for q in answered if q < day]
        if not prior:
            out[day] = cash[:]
            continue
        used = [q for q in answered if q <= prior[-1]]
        counts: dict[str, int] = {}
        for qday in used:
            policy = answers[qday]["policy"]
            counts[policy] = counts.get(policy, 0) + 1
        style = {"book": (counts.get("book", 0) + 1) / (len(used) + 1)}
        for policy, hits in counts.items():
            if policy != "book":
                style[policy] = hits / (len(used) + 1)
        prev = book_rows[day - 1] if day else cash
        built = {
            policy: _policy_row(policy, ids, book_rows[day], prev, mv_rows[day], ew_rows[day], live_rows[day])
            for policy in style
        }
        mixed = _mix_bps(style, built)
        row = mixed if mixed is not None else [int(v) for v in book_rows[day]]
        out[day] = _zero_dead(row, live_rows[day])
    return out


def select_question_dates(book, ew, book_net, bench, n=20, floor=0.02, sleeves=None):
    sleeves = list(sleeves or [col for col in book.columns if col != "cash_allocation"])
    cols = sleeves + ["cash_allocation"]
    values = book[cols].to_numpy(dtype=float)
    changes = np.zeros(len(values))
    for pos in range(1, len(values)):
        changes[pos] = np.abs(values[pos] - values[pos - 1]).sum()

    def pick(limit):
        ranked = [pos for pos in range(1, len(values)) if changes[pos] > limit]
        def score(pos):
            other = ew.iloc[pos][cols].to_numpy(dtype=float)
            gap = abs(float(book_net.iloc[pos]) - float(bench.iloc[pos]))
            return changes[pos] + 0.5 * np.abs(values[pos] - other).sum() + 0.5 * gap
        ranked.sort(key=score, reverse=True)
        kept = []
        vecs = []
        for pos in ranked:
            if any(np.max(np.abs(values[pos] - have)) <= 1e-3 for have in vecs):
                continue
            kept.append(pos)
            vecs.append(values[pos])
            if len(kept) == n:
                break
        return kept

    used = floor
    chosen = pick(floor)
    if len(chosen) < n and floor > 0.01:
        used = 0.01
        chosen = pick(0.01)
    dates = [book.index[pos] for pos in sorted(chosen)]
    return dates, used


def compound_index(weights, asset_returns, rf, costs, sleeves, lag=1, prev_zero=True, withhold=True):
    count = len(weights)
    wealth = 1.0
    out = np.full(count, np.nan)
    prev = np.zeros(len(sleeves)) if prev_zero else weights.iloc[0][sleeves].to_numpy(dtype=float)
    cost_vec = np.array([float(costs[name]) for name in sleeves])
    stopped = False
    for pos in range(count):
        if pos < lag:
            out[pos] = 1.0
            continue
        if stopped:
            continue
        decision = pos - lag
        held = weights.iloc[decision][sleeves].to_numpy(dtype=float)
        cash = float(weights.iloc[decision]["cash_allocation"])
        rets = asset_returns.iloc[pos][sleeves].to_numpy(dtype=float)
        if withhold and np.any((~np.isfinite(rets)) & (np.abs(held) > 1e-8)):
            stopped = True
            continue
        safe = np.where(np.isfinite(rets), rets, 0.0)
        change = np.abs(held - prev)
        cost = 0.0 if np.all(change <= 1e-12) else float(np.sum(change * cost_vec))
        rate = float(rf.iloc[pos]) if np.isfinite(rf.iloc[pos]) else 0.0
        gross = float(np.sum(held * safe) + cash * rate)
        wealth *= 1.0 + gross - cost
        out[pos] = wealth
        prev = held
    return pd.Series(out, index=weights.index)


def _load_weights(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.set_index("date").sort_index()


def _net_index_from_saved(total: pd.Series, cost: pd.Series) -> np.ndarray:
    wealth = 1.0
    out = []
    for gross, paid in zip(total.to_numpy(dtype=float), cost.to_numpy(dtype=float)):
        paid = 0.0 if not np.isfinite(paid) else float(paid)
        gross = 0.0 if not np.isfinite(gross) else float(gross)
        wealth *= 1.0 + gross - paid
        out.append(wealth)
    return np.array(out)


def _round_or_none(value, digits=8):
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), digits)


def export_replay(root: Path | None = None) -> Path:
    root = Path(root or ROOT)
    from src.core.data import DataPipeline
    from src.core.diagnostics import feature_tick_label
    from src.core.features import compute_asset_features, engineer_features
    from src.core.labels import get_plot_label
    from src.core.utils import load_config

    run_dir = root / "output" / "max_cap_tree"
    dest = root / "docs" / "sandbox" / "data" / "replay.json"
    log_path = run_dir / "sandbox_replay.log"
    cfg = load_config(
        root / "config" / "config.yaml",
        override_path=root / "config" / "config.attack.yaml",
        override_paths=[root / "config" / "config.max_capability.yaml"],
    )
    tiered = (cfg.get("portfolio") or {}).get("tiered_transaction_costs") or {}
    table = tiered.get("costs_by_asset") or {}
    default_cost = float(tiered.get("default_cost", 0.0005))

    minvar = _load_weights(run_dir / "results" / "test" / "minvar" / "portfolio_weights.csv")
    mv = _load_weights(run_dir / "results" / "test" / "mv" / "portfolio_weights.csv")
    ew = _load_weights(run_dir / "results" / "test" / "ew" / "portfolio_weights.csv")
    diag = pd.read_csv(run_dir / "results" / "test" / "minvar" / "optimizer_diagnostics.csv")
    saved_total = pd.read_csv(run_dir / "results" / "test" / "minvar" / "portfolio_total_returns.csv")
    saved_excess = pd.read_csv(run_dir / "results" / "test" / "minvar" / "portfolio_returns.csv")
    bench = pd.read_csv(run_dir / "results" / "test" / "benchmark_returns_panel.csv", parse_dates=["date"])
    bench = bench.set_index("date").sort_index()

    sleeves = [col for col in minvar.columns if col != "cash_allocation"]
    costs = {name: cost_for_asset(name, table, default_cost) for name in sleeves}
    loader = DataPipeline(config=cfg)
    start = (cfg.get("data") or {}).get("start_date", "1945-01-01")
    end = (cfg.get("data") or {}).get("end_date", "2025-11-28")
    try:
        panel = loader.load(start_date=start, end_date=end, strict_manifest=False)
    except TypeError:
        panel = loader.load(start_date=start, end_date=end)

    renamed = {}
    for col in panel.columns:
        if str(col).startswith("asset_"):
            renamed[col] = str(col).replace("asset_", "").upper()
    levels = panel.rename(columns=renamed)
    raw = levels[[name for name in sleeves if name in levels.columns]].pct_change()
    rf_cols = [col for col in panel.columns if "ancillary_risk_free" in str(col).lower()]
    if not rf_cols:
        raise RuntimeError("No ancillary risk-free series in the panel")
    rf = panel[rf_cols[0]].pct_change().ffill(limit=5)

    exec_dates = pd.to_datetime(saved_total["date"])
    decision_dates = minvar.index
    if len(exec_dates) != len(decision_dates):
        raise RuntimeError("Weight rows and return rows differ")
    # Row i is the return the decision on that row earns (already the next session).
    asset = raw.reindex(exec_dates).reset_index(drop=True)
    asset.index = decision_dates
    rf_aligned = rf.reindex(exec_dates).ffill(limit=5).reset_index(drop=True)
    rf_aligned.index = decision_dates

    built = compound_index(
        minvar, asset, rf_aligned, costs, sleeves, lag=0, prev_zero=True, withhold=False
    )
    saved_cost = diag["transaction_cost"].to_numpy(dtype=float)
    saved_net = saved_total["total_return"].to_numpy(dtype=float) - saved_cost
    # built[i+1] is the index after decision i. Compare daily nets.
    built_net = np.zeros(len(built))
    prev_wealth = 1.0
    for pos, value in enumerate(built.to_numpy(dtype=float)):
        built_net[pos] = value / prev_wealth - 1.0
        prev_wealth = value
    comparable = min(len(saved_net), len(built_net))
    gaps = np.abs(built_net[:comparable] - saved_net[:comparable])
    finite = np.isfinite(gaps)
    close = float(np.mean(gaps[finite] < 1e-4)) if finite.any() else 0.0
    saved_index = _net_index_from_saved(
        pd.Series(saved_total["total_return"]), pd.Series(saved_cost)
    )
    index_gap = abs(float(built.iloc[-1]) - float(saved_index[-1])) if np.isfinite(built.iloc[-1]) else 1.0
    log_path.write_text(
        f"return match {close:.4f} of days within 1e-4; index gap {index_gap:.6g}\n"
    )
    if close < 0.95 or index_gap > 1e-3:
        raise RuntimeError(
            f"Rebuilt book wealth does not match the save ({close:.4f}, gap {index_gap:.6g})"
        )

    def book_line(frame):
        series = compound_index(
            frame, asset, rf_aligned, costs, sleeves, lag=0, prev_zero=True, withhold=False
        )
        return [_round_or_none(value, 6) for value in series.tolist()]

    lines = {
        "book": book_line(minvar),
        "equal_weight": book_line(ew.reindex(decision_dates)),
        "mv": book_line(mv.reindex(decision_dates)),
    }
    for key, column in BENCH_LINES.items():
        aligned = bench[column].reindex(exec_dates).to_numpy(dtype=float)
        wealth = 1.0
        series = []
        for value in aligned:
            if np.isfinite(value):
                wealth *= 1.0 + float(value)
            series.append(round(wealth, 6))
        # Bench row 0 is the first panel date, which may be the decision date.
        # Store it on the decision index by using the exec-aligned series of equal length.
        lines[key] = series

    book_net = pd.Series(saved_net, index=decision_dates)
    sixty = bench["60_40"].reindex(exec_dates)
    sixty.index = decision_dates
    picked, floor = select_question_dates(
        minvar, ew.reindex(decision_dates), book_net, sixty.fillna(0.0), sleeves=sleeves
    )
    asset_features, macro_features = engineer_features(panel, cfg)
    checkpoint = json.loads(
        (root / "output" / "wf_checkpoints" / "max_cap_tree" / "wf_checkpoint.json").read_text()
    )
    probs = checkpoint.get("forecast_probs") or {}
    diag_path = root / "output" / "max_cap_tree" / "diagnostics" / "test" / "xgb_diagnostics.json"
    diagnostics = json.loads(diag_path.read_text()) if diag_path.is_file() else {}

    def label_of(name: str) -> str:
        return desk_name(name)

    def feature_row(day: pd.Timestamp, sleeve: str):
        frame = asset_features.get(sleeve)
        if frame is None:
            return None
        stamp = pd.Timestamp(day)
        if stamp not in frame.index or stamp not in macro_features.index:
            return None
        asset_row = frame.loc[stamp]
        macro_row = macro_features.loc[stamp]
        chosen = []
        for fid in ASSET_FEATURE_IDS:
            if fid not in asset_row.index:
                continue
            value = asset_row[fid]
            if np.isfinite(value):
                chosen.append({"id": fid, "label": feature_tick_label(fid), "value": round(float(value), 6)})
        for fid in MACRO_FEATURE_IDS:
            if fid not in macro_row.index:
                continue
            value = macro_row[fid]
            if np.isfinite(value):
                full = f"macro_{fid}"
                chosen.append({"id": full, "label": feature_tick_label(full), "value": round(float(value), 6)})
        if not any(item["id"] == "avg_return_hl21" for item in chosen):
            return None
        if len(chosen) < 3:
            return None
        return chosen

    def regime_word(day: pd.Timestamp, sleeve: str):
        if sleeve in {"US_CASH", "cash_allocation"}:
            return None
        blob = None
        for key, value in probs.items():
            token = str(key).upper().replace("_TOTAL_RETURN", "").replace("_RETURN", "")
            if token == sleeve or str(key) == sleeve:
                blob = value
                break
        if not blob:
            return None
        index = [str(item)[:10] for item in blob.get("index") or []]
        stamp = str(pd.Timestamp(day).date())
        if stamp not in index:
            return None
        row = blob["data"][index.index(stamp)]
        names = ["calm", "inflationary", "crisis"]
        return names[int(np.argmax(row[:3]))]

    questions = []
    skipped = []
    for day in picked:
        loc = minvar.index.get_loc(day)
        if isinstance(loc, slice):
            loc = loc.start
        current = minvar.iloc[loc][sleeves + ["cash_allocation"]].to_numpy(dtype=float)
        previous = (
            minvar.iloc[loc - 1][sleeves + ["cash_allocation"]].to_numpy(dtype=float)
            if loc
            else np.r_[np.zeros(len(sleeves)), 1.0]
        )
        delta = np.abs(current - previous)
        order = np.argsort(-delta)
        top = float(delta[order[0]])
        sleeve_ids = sleeves + ["cash_allocation"]
        tied = [sleeve_ids[pos] for pos in order if abs(float(delta[pos]) - top) <= 1e-12]
        tied.sort(key=lambda name: (name not in TREE_SLEEVES, name))
        sleeve = tied[0]
        feature_sleeve = sleeve
        if feature_sleeve == "cash_allocation" or asset_features.get(feature_sleeve) is None:
            feature_sleeve = next(
                (
                    name
                    for name in (sleeve_ids[pos] for pos in order)
                    if name != "cash_allocation" and asset_features.get(name) is not None
                ),
                sleeves[0],
            )
        features = feature_row(day, feature_sleeve)
        if not features:
            skipped.append(str(pd.Timestamp(day).date()))
            continue
        ids = sleeve_ids
        menu = menu_choices(
            ids,
            previous,
            current,
            mv.iloc[loc][ids].to_numpy(dtype=float),
            ew.iloc[loc][ids].to_numpy(dtype=float),
        )
        seed = int(hashlib.sha256(str(pd.Timestamp(day).date()).encode()).hexdigest()[:8], 16)
        random.Random(seed).shuffle(menu)
        book_bps = to_bps(current)
        regime = regime_word(day, sleeve)
        feature_payload = [
            {"id": item["id"], "label": item["label"], "value": item["value"]} for item in features
        ]
        evidence = _question_evidence(
            day, feature_sleeve, feature_payload, probs, diagnostics, sleeves, label_of
        )
        questions.append(
            {
                "date": str(pd.Timestamp(day).date()),
                "sleeve": sleeve,
                "sleeve_label": label_of(feature_sleeve),
                "regime": regime if sleeve not in {"US_CASH", "cash_allocation"} else None,
                "features": feature_payload,
                "previous_bps": to_bps(previous),
                "book_bps": book_bps,
                "prompt": format_prompt(
                    label_of(feature_sleeve),
                    str(pd.Timestamp(day).date()),
                    feature_payload,
                    regime if sleeve not in {"US_CASH", "cash_allocation"} else None,
                    cash_moved=sleeve == "cash_allocation",
                ),
                "choices": [
                    {
                        "policy": policy,
                        "headline": choice_lines(previous, vector, ids, label_of)[0],
                        "sleeves": choice_lines(previous, vector, ids, label_of)[1],
                        "bps": to_bps(vector),
                        "miss": explain_miss(book_bps, to_bps(vector), ids, evidence, label_of),
                    }
                    for policy, vector in menu
                ],
            }
        )
    if len(questions) < 20:
        log_path.write_text(
            log_path.read_text() + f"questions {len(questions)} floor {floor} skipped {skipped}\n"
        )
        raise RuntimeError(f"Need 20 questions, built {len(questions)}")

    questions = questions[:20]

    def panel_bps(frame) -> list[list[int]]:
        aligned = frame.reindex(decision_dates)
        cols = sleeves + ["cash_allocation"]
        rows = []
        for pos in range(len(decision_dates)):
            values = aligned.iloc[pos][cols].to_numpy(dtype=float)
            values = np.where(np.isfinite(values), values, 0.0)
            if float(values.sum()) <= 1e-8:
                values = np.zeros(len(cols))
                values[-1] = 1.0
            rows.append(to_bps(values))
        return rows
    returns = []
    live = []
    for pos in range(len(decision_dates)):
        row = asset.iloc[pos]
        returns.append([_round_or_none(row[name] if name in row.index else np.nan) for name in sleeves])
        live.append([bool(np.isfinite(row[name])) if name in row.index else False for name in sleeves])
    payload = {
        "execution_lag_days": 1,
        "note": "A match on all 20 dates uses FIOracle's weights on those dates. FIOracle traded on other days as well.",
        "sleeves": [
            {"id": name, "label": label_of(name), "cost": costs[name]} for name in sleeves
        ] + [{"id": "cash_allocation", "label": desk_name("cash_allocation"), "cost": 0.0}],
        "dates": [str(day.date()) for day in decision_dates],
        "exec_dates": [str(pd.Timestamp(day).date()) for day in exec_dates],
        "returns": returns,
        "rf": [_round_or_none(value, 8) for value in rf_aligned.tolist()],
        "live": live,
        "lines": lines,
        "questions": questions,
        "book_bps": panel_bps(minvar),
        "mv_bps": panel_bps(mv),
        "ew_bps": panel_bps(ew),
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload["sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
    dest.write_text(json.dumps(payload, separators=(",", ":")))
    log_path.write_text(
        log_path.read_text()
        + f"Wrote {len(questions)} questions at floor {floor}. Skipped {skipped}.\n"
    )
    return dest


def main() -> None:
    export_replay()


if __name__ == "__main__":
    main()
