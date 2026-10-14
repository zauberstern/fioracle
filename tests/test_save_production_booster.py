"""The production booster is written so a later page can load it."""

import json

import numpy as np
import pandas as pd
import xgboost as xgb

from src.core.booster_io import save_production_booster


def test_save_production_booster_writes_json_and_column_order(tmp_path):
    X = pd.DataFrame(
        {
            "avg_return_hl5": np.linspace(-1.0, 1.0, 30),
            "macro_vix_level_norm": np.linspace(0.0, 1.0, 30),
        }
    )
    y = pd.Series(([0, 1, 2] * 10))
    model = xgb.XGBClassifier(
        n_estimators=2,
        max_depth=2,
        objective="multi:softprob",
        num_class=3,
        verbosity=0,
    )
    model.fit(X, y)

    save_production_booster(
        model,
        asset_id="BBG_US_TREASURY",
        feature_names=list(X.columns),
        class_map={0: 0, 1: 1, 2: 2},
        n_estimators=2,
        models_dir=tmp_path,
    )

    booster = xgb.Booster()
    booster.load_model(str(tmp_path / "BBG_US_TREASURY.json"))
    schema = json.loads((tmp_path / "BBG_US_TREASURY.schema.json").read_text())
    assert schema["feature_names"] == ["avg_return_hl5", "macro_vix_level_norm"]
    assert schema["n_estimators"] == 2
    assert schema["asset_id"] == "BBG_US_TREASURY"
    assert booster.num_features() == 2
