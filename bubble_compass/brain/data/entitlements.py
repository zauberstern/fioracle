"""WRDS / LSEG entitlement probe. Never writes secrets to disk."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol


class LibraryClient(Protocol):
    def list_libraries(self) -> list[str]: ...

    def list_tables(self, library: str) -> list[str]: ...


# Documented baseline from paper/notes/wrds_inventory.md (July 2026).
DEFAULT_INVENTORY: dict[str, str] = {
    "trace_enhanced": "have",
    "frb": "have",
    "crsp.dsi": "have",
    "crsp.dsf": "have",
    "crsp.sfz_dind": "denied",
    "optionm": "have",
    "msrb": "have",
    "fisd": "sample",
    "frb_st_louis.fred_vintages": "missing",
    "comp": "unknown",
    "ibes": "unknown",
}

LIBRARY_ALIASES: dict[str, str] = {
    "compustat": "comp",
    "optionmetrics": "optionm",
}


@dataclass
class ProbeResult:
    libraries: dict[str, dict[str, Any]] = field(default_factory=dict)
    lseg: dict[str, Any] = field(default_factory=dict)
    probed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _lib_key(name: str) -> str:
    return LIBRARY_ALIASES.get(name.lower(), name.lower())


def probe_from_inventory_and_client(
    *,
    inventory: Mapping[str, str] | None = None,
    client: LibraryClient | None = None,
    lseg_credential_path: Path | None = None,
) -> ProbeResult:
    inv = dict(inventory or DEFAULT_INVENTORY)
    libraries: dict[str, dict[str, Any]] = {}

    listed: set[str] = set()
    if client is not None:
        try:
            listed = {_lib_key(x) for x in client.list_libraries()}
        except Exception as exc:  # why: live WRDS can fail without killing offline path
            libraries["_probe_error"] = {
                "status": "error",
                "detail": type(exc).__name__,
            }

    for key, status in inv.items():
        base = key.split(".")[0]
        entry: dict[str, Any] = {"status": status, "tables": []}
        if client is not None and base in listed:
            try:
                tables = list(client.list_tables(base))
            except Exception:
                tables = []
            entry["tables"] = tables
            # Live listing overrides unknown / missing when the library answers.
            if status in ("unknown", "missing") and tables:
                entry["status"] = "have"
            elif status == "unknown" and base in listed:
                entry["status"] = "have"
            # Denied inventory stays denied even if list_tables returns something.
            if status == "denied":
                entry["status"] = "denied"
        libraries[key] = entry

    # Promote bare library names discovered live but not in inventory.
    if client is not None:
        for lib in listed:
            if lib not in libraries and f"{lib}" not in libraries:
                if any(k.startswith(f"{lib}.") or k == lib for k in libraries):
                    continue
                try:
                    tables = list(client.list_tables(lib))
                except Exception:
                    tables = []
                if lib in ("comp", "ibes", "optionm"):
                    libraries[lib] = {"status": "have" if tables else "unknown", "tables": tables}

    # Explicit comp/ibes from fake client: if inventory unknown and listed, mark have.
    for special in ("comp", "ibes"):
        if special in listed and special in libraries:
            if libraries[special]["status"] == "unknown":
                libraries[special]["status"] = "have"
                if not libraries[special]["tables"]:
                    try:
                        libraries[special]["tables"] = list(client.list_tables(special))  # type: ignore[union-attr]
                    except Exception:
                        pass

    lseg_path = Path(lseg_credential_path or Path("config/lseg_credentials.yaml"))
    if lseg_path.is_file():
        lseg = {"status": "credentials_present", "path": str(lseg_path.name)}
    else:
        lseg = {"status": "missing_credentials"}

    return ProbeResult(
        libraries=libraries,
        lseg=lseg,
        probed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def write_entitlements(result: ProbeResult, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def try_live_wrds_client(dotenv_path: Path | None = None) -> LibraryClient | None:
    """Return a live wrds client or None if credentials / package unavailable."""
    try:
        from src.data.wrds_ingest import WrdsConnection

        conn = WrdsConnection.from_env(dotenv_path=dotenv_path)
        client = conn._client
        if client is None:
            return None
        # Adapt wrds.Connection which uses list_libraries / list_tables.
        return client  # type: ignore[return-value]
    except Exception:
        return None
