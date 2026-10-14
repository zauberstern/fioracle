"""Copy a finished run's probabilities and minimum-variance weights into the sandbox folder."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.labels import get_plot_label

CASH_IDS = {"US_CASH", "US_CASH_RETURN", "cash_allocation"}
FEATURES_ONLY = {
    "CHF",
    "CHF_TOTAL_RETURN",
    "USD_SWAPTION_1Y_5Y",
    "USD_SWAPTION_1Y_5Y_TOTAL_RETURN",
    "USD_SWAPTION_1Y_10Y",
    "USD_SWAPTION_1Y_10Y_TOTAL_RETURN",
    "USD_SWAPTION_6M_5Y",
    "USD_SWAPTION_6M_5Y_TOTAL_RETURN",
    "VRP_HARVEST",
    "VRP_HARVEST_TOTAL_RETURN",
    "WTI",
    "WTI_TOTAL_RETURN",
}
REQUESTED_DATES = ("2008-09-15", "2020-03-16", "2022-01-03")
LABEL_IDS = {
    "US_CASH": "US_CASH_RETURN",
    "US_10Y_GOV_BOND": "US_10Y_GOV_BOND_RETURN",
    "ISHARES_20Y_TREASURY": "ISHARES_20Y_TREASURY_TOTAL_RETURN",
    "ISHARES_7_10Y_TREASURY": "ISHARES_7_10Y_TREASURY_TOTAL_RETURN",
    "ISHARES_1_3Y_TREASURY": "ISHARES_1_3Y_TREASURY_TOTAL_RETURN",
    "BBG_US_TREASURY": "BBG_US_TREASURY_TOTAL_RETURN",
    "US_BOND_AGG": "US_BOND_AGG_TOTAL_RETURN",
    "VANGUARD_TOTAL_BOND": "VANGUARD_TOTAL_BOND_TOTAL_RETURN",
    "BBG_US_CORPORATE": "BBG_US_CORPORATE_TOTAL_RETURN",
    "BBG_GLOBAL_AGG": "BBG_GLOBAL_AGG_TOTAL_RETURN",
    "BBG_US_HIGH_YIELD": "BBG_US_HIGH_YIELD_TOTAL_RETURN",
    "BBG_EM_USD_AGG": "BBG_EM_USD_AGG_TOTAL_RETURN",
    "US_TIPS_0_5": "US_TIPS_0_5_TOTAL_RETURN",
    "GLOBAL_ILB_0_5": "GLOBAL_ILB_0_5_TOTAL_RETURN",
    "ISHARES_SWISS_GOV_7_15": "ISHARES_SWISS_GOV_7_15_TOTAL_RETURN",
    "GOLD": "GOLD_TOTAL_RETURN",
    "cash_allocation": "US_CASH_RETURN",
}


def snap_on_or_before(dates, target: str):
    hits = sorted(d for d in dates if str(d)[:10] <= target[:10])
    if not hits:
        return None
    return str(hits[-1])[:10]


def _label(asset_id: str) -> str:
    if asset_id == "cash_allocation":
        return "Cash residual"
    return get_plot_label(LABEL_IDS.get(asset_id, asset_id))


def _probs_for_date(blob: dict, day: str):
    index = [str(x)[:10] for x in blob.get("index") or []]
    if day not in index:
        return None
    row = blob["data"][index.index(day)]
    cols = [int(c) for c in blob.get("columns") or [0, 1, 2]]
    by_col = {cols[i]: float(row[i]) for i in range(min(len(cols), len(row)))}
    return {
        "p_calm": by_col.get(0),
        "p_inflationary": by_col.get(1),
        "p_crisis": by_col.get(2),
    }


def export_bundle(
    run_dir: Path,
    checkpoint_path: Path,
    dest: Path,
    max_weight: float,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "sandbox_export.log"
    if not checkpoint_path.exists():
        log_path.write_text(f"No checkpoint at {checkpoint_path}\n")
        return
    raw = json.loads(checkpoint_path.read_text())
    probs = raw.get("forecast_probs") or {}
    if not probs:
        log_path.write_text("Checkpoint has no forecast_probs.\n")
        return

    weight_path = run_dir / "results" / "test" / "minvar" / "portfolio_weights.csv"
    if not weight_path.exists():
        log_path.write_text(f"No weights at {weight_path}\n")
        return
    weights = pd.read_csv(weight_path)
    date_col = weights.columns[0]
    weights[date_col] = weights[date_col].astype(str).str.slice(0, 10)
    weight_days = weights[date_col].tolist()
    prob_days = []
    for blob in probs.values():
        prob_days.extend(str(x)[:10] for x in (blob.get("index") or []))
    universe = sorted(set(weight_days) & set(prob_days))
    if not universe:
        universe = sorted(set(weight_days))
    chosen = []
    for target in list(REQUESTED_DATES) + ([universe[-1]] if universe else []):
        day = snap_on_or_before(universe, target)
        if day and day not in chosen:
            chosen.append(day)
    if not chosen:
        log_path.write_text("No overlapping dates in weights and probabilities.\n")
        return

    asset_order = [c for c in weights.columns if c != date_col]
    by_date = {}
    for day in chosen:
        wrow = weights.loc[weights[date_col] == day].iloc[-1]
        assets = []
        for asset_id, blob in probs.items():
            got = _probs_for_date(blob, day)
            if got is None:
                continue
            assets.append({"id": asset_id, "label": _label(asset_id), **got})
        weight_rows = []
        for asset_id in asset_order:
            weight_rows.append(
                {
                    "id": asset_id,
                    "label": _label(asset_id),
                    "weight": float(wrow[asset_id]),
                    "cash": asset_id in CASH_IDS,
                    "features_only": asset_id in FEATURES_ONLY,
                }
            )
        by_date[day] = {"assets": assets, "weights": weight_rows}

    trees = dest / "trees"
    if trees.exists():
        shutil.rmtree(trees)
    trees.mkdir()
    models = run_dir / "models"
    copied = []
    if models.exists():
        for path in sorted(models.glob("*.json")):
            if path.name.endswith(".schema.json"):
                continue
            schema = path.with_name(path.stem + ".schema.json")
            if not schema.exists():
                continue
            shutil.copy2(path, trees / path.name)
            shutil.copy2(schema, trees / schema.name)
            copied.append(path.stem)

    last = chosen[-1]
    payload = {
        "as_of": last,
        "max_weight": max_weight,
        "dates": chosen,
        "assets": by_date[last]["assets"],
        "weights": by_date[last]["weights"],
        "by_date": by_date,
        "trees": copied,
    }
    (dest / "baseline.json").write_text(json.dumps(payload))
    log_path.write_text(
        f"Wrote {len(chosen)} dates and {len(copied)} boosters from {run_dir}.\n"
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    from src.core.utils import load_config

    cfg = load_config(
        root / "config" / "config.yaml",
        override_path=root / "config" / "config.attack.yaml",
        override_paths=[root / "config" / "config.max_capability.yaml"],
    )
    cap = float((cfg.get("portfolio") or {}).get("max_weight") or 0.20)
    export_bundle(
        run_dir=root / "output" / "max_cap_tree",
        checkpoint_path=root / "output" / "wf_checkpoints" / "max_cap_tree" / "wf_checkpoint.json",
        dest=root / "docs" / "sandbox" / "data",
        max_weight=cap,
    )


if __name__ == "__main__":
    main()
