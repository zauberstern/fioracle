"""Entitlement probe writes have/denied/sample without secrets."""
from __future__ import annotations

import json
from pathlib import Path

from bubble_compass.brain.data.entitlements import (
    ProbeResult,
    probe_from_inventory_and_client,
    write_entitlements,
)


class _FakeListClient:
    """Simulates wrds.Connection.list_libraries / list_tables."""

    def list_libraries(self) -> list[str]:
        return ["trace_enhanced", "frb", "crsp", "comp", "ibes", "optionm"]

    def list_tables(self, library: str) -> list[str]:
        tables = {
            "trace_enhanced": ["trace_enhanced"],
            "frb": ["rates_daily"],
            "crsp": ["dsi", "dsf", "sfz_dind"],
            "comp": ["funda"],
            "ibes": ["statsum_epsus"],
            "optionm": ["opprcd"],
        }
        return tables.get(library, [])


def test_probe_marks_known_wrds_libraries(tmp_path: Path) -> None:
    inventory = {
        "trace_enhanced": "have",
        "frb": "have",
        "crsp.dsi": "have",
        "crsp.sfz_dind": "denied",
        "optionm": "have",
        "comp": "unknown",
        "ibes": "unknown",
    }
    result = probe_from_inventory_and_client(
        inventory=inventory,
        client=_FakeListClient(),
        lseg_credential_path=tmp_path / "missing_lseg.yaml",
    )
    assert result.libraries["trace_enhanced"]["status"] == "have"
    assert result.libraries["crsp.sfz_dind"]["status"] == "denied"
    assert result.libraries["comp"]["status"] == "have"
    assert result.libraries["ibes"]["status"] == "have"
    assert result.lseg["status"] == "missing_credentials"
    assert "password" not in json.dumps(result.to_dict()).lower()
    assert "secret" not in json.dumps(result.to_dict()).lower()


def test_write_entitlements_json(tmp_path: Path) -> None:
    result = ProbeResult(
        libraries={"trace_enhanced": {"status": "have", "tables": ["trace_enhanced"]}},
        lseg={"status": "missing_credentials"},
        probed_at="2026-01-01T00:00:00Z",
    )
    out = write_entitlements(result, tmp_path / "entitlements.json")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["libraries"]["trace_enhanced"]["status"] == "have"
    assert payload["lseg"]["status"] == "missing_credentials"
