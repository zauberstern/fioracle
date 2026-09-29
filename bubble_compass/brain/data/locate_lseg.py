"""Locate LSEG panels on disk and register under lake bronze (symlink preferred)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

PANEL_NAMES = (
    "lseg_eq_ohlc_unadj",
    "lseg_eq_ohlc_corax",
    "lseg_eq_spread",
    "lseg_eq_size",
    "lseg_spx_pit",
    "lseg_gics",
    "lseg_index_vol_rates",
    "lseg_ibes",
    "lseg_estimates",
    "lseg_worldscope",
    "lseg_dividends",
)


def _find_panel(roots: Iterable[Path], stem: str) -> Path | None:
    name = f"{stem}.parquet"
    for root in roots:
        if not root.is_dir():
            continue
        direct = root / "data" / "macro" / name
        if direct.is_file():
            return direct
        for hit in root.rglob(name):
            if hit.is_file():
                return hit
    return None


def locate_and_register_lseg(
    *,
    search_roots: list[Path],
    bronze_dir: Path,
) -> dict:
    bronze_dir = Path(bronze_dir)
    bronze_dir.mkdir(parents=True, exist_ok=True)
    panels: dict[str, dict] = {}
    for stem in PANEL_NAMES:
        found = _find_panel(search_roots, stem)
        if found is None:
            panels[stem] = {"status": "missing", "source": None}
            continue
        dest = bronze_dir / f"{stem}.parquet"
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        try:
            os.symlink(found.resolve(), dest)
            link_kind = "symlink"
        except OSError:
            # Fallback: write a pointer JSON if symlink fails (cross-device).
            dest = bronze_dir / f"{stem}.pointer.json"
            dest.write_text(
                json.dumps({"source": str(found.resolve())}, indent=2) + "\n",
                encoding="utf-8",
            )
            link_kind = "pointer"
        panels[stem] = {
            "status": "registered",
            "source": str(found.resolve()),
            "registered_as": str(dest),
            "link_kind": link_kind,
        }

    # IPA surface directory
    ipa_status = {"status": "missing", "source": None}
    for root in search_roots:
        ipa = root / "data" / "macro" / "lseg_ipa_surface"
        if ipa.is_dir():
            pointer = bronze_dir / "lseg_ipa_surface.pointer.json"
            pointer.write_text(
                json.dumps({"source": str(ipa.resolve())}, indent=2) + "\n",
                encoding="utf-8",
            )
            ipa_status = {
                "status": "registered",
                "source": str(ipa.resolve()),
                "registered_as": str(pointer),
                "link_kind": "pointer",
            }
            break
    panels["lseg_ipa_surface"] = ipa_status

    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_registered": sum(1 for p in panels.values() if p.get("status") == "registered"),
        "panels": panels,
    }
    (bronze_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
