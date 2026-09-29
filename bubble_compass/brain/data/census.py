"""Disk census for Bubble Compass data sources → CATALOG.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd


def _series_id_from_csv(path: Path) -> str:
    return path.stem


def _csv_meta(path: Path) -> dict[str, Any]:
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return {
            "series_id": _series_id_from_csv(path),
            "path": str(path),
            "kind": "csv",
            "rows": 0,
            "span_start": None,
            "span_end": None,
            "error": type(exc).__name__,
            "wired": False,
        }
    date_col = None
    for candidate in ("date", "Date", "DATE", "event_date", "effective_date"):
        if candidate in df.columns:
            date_col = candidate
            break
    span_start = span_end = None
    if date_col is not None:
        dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if not dates.empty:
            span_start = str(dates.min().date())
            span_end = str(dates.max().date())
    return {
        "series_id": _series_id_from_csv(path),
        "path": str(path),
        "kind": "csv",
        "rows": int(len(df)),
        "span_start": span_start,
        "span_end": span_end,
        "wired": False,
    }


def _parquet_meta(path: Path, series_id: str | None = None) -> dict[str, Any]:
    try:
        df = pd.read_parquet(path)
    except Exception as exc:
        return {
            "series_id": series_id or path.stem,
            "path": str(path),
            "kind": "parquet",
            "rows": 0,
            "span_start": None,
            "span_end": None,
            "error": type(exc).__name__,
            "wired": False,
        }
    sid = series_id
    if sid is None and "series_id" in df.columns and not df.empty:
        sid = str(df["series_id"].iloc[0])
    sid = sid or path.stem
    date_col = None
    for candidate in ("event_date", "effective_date", "date", "available_date"):
        if candidate in df.columns:
            date_col = candidate
            break
    span_start = span_end = None
    if date_col is not None:
        dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if not dates.empty:
            span_start = str(dates.min().date())
            span_end = str(dates.max().date())
    return {
        "series_id": sid,
        "path": str(path),
        "kind": "parquet",
        "rows": int(len(df)),
        "span_start": span_start,
        "span_end": span_end,
        "wired": False,
    }


def _scan_csv_dir(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        return []
    return [_csv_meta(p) for p in sorted(directory.glob("*.csv"))]


def _scan_lake_observations(lake_dir: Path) -> list[dict[str, Any]]:
    root = lake_dir / "bronze" / "observations"
    if not root.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for series_dir in sorted(root.glob("series_id=*")):
        parquet = series_dir / "data.parquet"
        if not parquet.is_file():
            continue
        sid = series_dir.name.split("=", 1)[-1]
        entries.append(_parquet_meta(parquet, series_id=sid))
    return entries


def _scan_wrds_enrichment(lake_dir: Path) -> list[dict[str, Any]]:
    root = lake_dir / "bronze" / "wrds_enrichment"
    if not root.is_dir():
        return []
    return [
        _parquet_meta(p, series_id=f"wrds_{p.stem}")
        for p in sorted(root.glob("*.parquet"))
    ]


def _scan_data_v3(data_v3_dir: Path) -> list[dict[str, Any]]:
    if not data_v3_dir.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for parquet in sorted(data_v3_dir.rglob("*.parquet"))[:200]:
        # Cap recursive walk for huge IPA trees; full IPA is noted as a directory entry.
        if "lseg_ipa_surface" in str(parquet):
            continue
        entries.append(_parquet_meta(parquet, series_id=f"data_v3_{parquet.stem}"))
    ipa = data_v3_dir / "data" / "macro" / "lseg_ipa_surface"
    if not ipa.is_dir():
        ipa = data_v3_dir / "data" / "macro"
    # Count IPA files if present under data_v3
    ipa_files = list(data_v3_dir.rglob("ric=*"))[:1]
    if ipa_files or (data_v3_dir / "data" / "macro" / "lseg_ipa_surface").exists():
        ipa_root = data_v3_dir / "data" / "macro" / "lseg_ipa_surface"
        n = sum(1 for _ in ipa_root.rglob("*") if _.is_file()) if ipa_root.is_dir() else 0
        if n:
            entries.append(
                {
                    "series_id": "lseg_ipa_surface",
                    "path": str(ipa_root),
                    "kind": "directory",
                    "rows": n,
                    "span_start": None,
                    "span_end": None,
                    "wired": False,
                }
            )
    return entries


def _scan_extra_roots(roots: Sequence[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for root in roots:
        if not root.is_dir():
            entries.append(
                {
                    "series_id": f"extra_{root.name}",
                    "path": str(root),
                    "kind": "missing",
                    "rows": 0,
                    "span_start": None,
                    "span_end": None,
                    "wired": False,
                }
            )
            continue
        entries.append(
            {
                "series_id": f"extra_{root.name}",
                "path": str(root),
                "kind": "directory",
                "rows": sum(1 for _ in root.rglob("*") if _.is_file()),
                "span_start": None,
                "span_end": None,
                "wired": False,
            }
        )
    return entries


def census_sources(
    *,
    root: Path,
    asset_dir: Path | None = None,
    macro_dir: Path | None = None,
    lake_dir: Path | None = None,
    data_v3_dir: Path | None = None,
    extra_roots: Iterable[Path] | None = None,
    wired_series_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    root = Path(root)
    asset_dir = Path(asset_dir or root / "asset_universe")
    macro_dir = Path(macro_dir or root / "macro_universe")
    lake_dir = Path(lake_dir or root / "data" / "lake")
    data_v3_dir = Path(data_v3_dir or root / "data" / "data_v3")
    extras = list(extra_roots or [])
    wired = set(wired_series_ids or [])

    entries: list[dict[str, Any]] = []
    entries.extend(_scan_csv_dir(asset_dir))
    entries.extend(_scan_csv_dir(macro_dir))
    entries.extend(_scan_lake_observations(lake_dir))
    entries.extend(_scan_wrds_enrichment(lake_dir))
    entries.extend(_scan_data_v3(data_v3_dir))
    entries.extend(_scan_extra_roots(extras))

    for entry in entries:
        if entry["series_id"] in wired:
            entry["wired"] = True

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": str(root),
        "n_entries": len(entries),
        "n_wired": sum(1 for e in entries if e.get("wired")),
        "entries": entries,
    }


def write_catalog(catalog: dict[str, Any], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    return path
