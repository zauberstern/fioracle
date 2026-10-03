"""Static Pages export from history parquet."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _load_export_module():
    path = ROOT / "scripts" / "export_compass_pages.py"
    spec = importlib.util.spec_from_file_location("export_compass_pages", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_export_asset_writes_layers(tmp_path: Path) -> None:
    export_asset = _load_export_module().export_asset
    history = tmp_path / "history"
    for layer in ("dlinear", "bsadf", "sentiment"):
        dest = history / layer
        dest.mkdir(parents=True)
        pd.DataFrame(
            {
                "as_of": pd.to_datetime(["2008-09-12", "2008-09-15"]),
                "residual_z": [0.1, 1.2] if layer == "dlinear" else [None, None],
                "bsadf_stat": [1.0, 2.5] if layer == "bsadf" else [None, None],
                "unavailable": [True, True] if layer == "sentiment" else [None, None],
            }
        ).to_parquet(dest / "SPY.parquet", index=False)

    out = tmp_path / "out" / "history"
    entry = export_asset("SPY", history, out)
    payload = json.loads((out / "SPY.json").read_text(encoding="utf-8"))
    assert payload["asset"] == "SPY"
    assert "dlinear" in payload["layers"]
    assert entry["n_rows"] == 2
    assert payload["layers"]["sentiment"][0]["unavailable"] is True
