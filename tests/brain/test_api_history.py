"""API /history and /as-of endpoints read layer parquet."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from bubble_compass.brain.api import server


def test_history_and_as_of(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache"
    for layer in ("dlinear", "bsadf", "lppls", "sentiment", "regime"):
        dest = cache / "history" / layer
        dest.mkdir(parents=True)
        pd.DataFrame(
            {
                "as_of": pd.to_datetime(["2008-09-12", "2008-09-15", "2008-09-16"]),
                "residual_z": [0.1, 1.2, 2.0] if layer == "dlinear" else [None, None, None],
                "bsadf_stat": [1.0, 2.5, 3.0] if layer == "bsadf" else [None, None, None],
                "critical_value": [2.0, 2.0, 2.0] if layer == "bsadf" else [None, None, None],
                "bubble_flag": [False, True, True] if layer == "bsadf" else [None, None, None],
                "lpp_confidence": [0.1, 0.4, 0.7] if layer == "lppls" else [None, None, None],
                "sentiment_velocity": [0.0, 0.1, 0.2] if layer == "sentiment" else [None, None, None],
                "unavailable": [True, True, True] if layer == "sentiment" else [None, None, None],
                "regime_state": ["normal", "boom", "bust"] if layer == "regime" else [None, None, None],
                "regime_confidence": [0.5, 0.6, 0.7] if layer == "regime" else [None, None, None],
            }
        ).to_parquet(dest / "SP500_TOTAL_RETURN.parquet", index=False)

    (cache / "manifest.json").write_text(
        json.dumps([{"asset": "SP500_TOTAL_RETURN", "as_of": "2008-09-16"}]),
        encoding="utf-8",
    )
    monkeypatch.setenv(server.CACHE_ENV, str(cache))

    with TestClient(server.app) as client:
        hist = client.get("/api/v1/history/SP500_TOTAL_RETURN")
        assert hist.status_code == 200
        body = hist.json()
        assert "dlinear" in body["layers"]
        assert len(body["layers"]["dlinear"]) == 3

        asof = client.get("/api/v1/as-of/SP500_TOTAL_RETURN", params={"date": "2008-09-14"})
        assert asof.status_code == 200
        tip = asof.json()
        assert tip["as_of"] == "2008-09-12"
        assert tip["state"]["bsadf"]["bubble_flag"] is False

        # Must not see 2008-09-15 when asking for 2008-09-14
        assert tip["state"]["bsadf"]["bsadf_stat"] == 1.0
