"""Persist a fitted XGBoost booster and the column order it expects."""

from __future__ import annotations

import json
from pathlib import Path


def save_production_booster(
    model,
    asset_id: str,
    feature_names: list,
    class_map: dict,
    n_estimators,
    models_dir,
) -> None:
    dest = Path(models_dir)
    dest.mkdir(parents=True, exist_ok=True)
    model.get_booster().save_model(str(dest / f"{asset_id}.json"))
    schema = {
        "asset_id": asset_id,
        "feature_names": list(feature_names),
        "class_map": {str(k): int(v) for k, v in class_map.items()},
        "n_estimators": None if n_estimators is None else int(n_estimators),
    }
    (dest / f"{asset_id}.schema.json").write_text(json.dumps(schema, indent=2))
