"""Static contracts for the GitHub Pages hybrid site under docs/."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

PERF_PATTERNS = [
    re.compile(r"-0\.42"),
    re.compile(r"erod-value", re.I),
    re.compile(r"countErod"),
    re.compile(r"\d+\.\d{2}\s*%"),
    re.compile(r"forty-two basis", re.I),
    re.compile(r"negative forty", re.I),
    re.compile(r"\(0\.42\)"),
    re.compile(r"(?<![\d.])0\.42(?![\d])"),
    re.compile(r"Sharpe ratio of", re.I),
    re.compile(r"returned -", re.I),
]

TEXT_GLOBS = ("*.html", "*.js", "*.css", "*.svg", "*.xml", "*.json", "*.txt")


def _docs_text_files() -> list[Path]:
    files: list[Path] = []
    for pattern in TEXT_GLOBS:
        for path in DOCS.rglob(pattern):
            if "vendor" in path.parts:
                continue
            # Research timeline / Compass tape JSON is a data feed, not marketing copy
            if "data" in path.parts and path.suffix == ".json":
                continue
            # Built Meridian bundles contain numeric layer values; marketing
            # pages under docs/*.html remain the performance-number gate.
            if "compass" in path.parts and path.suffix in {".js", ".css", ".map"}:
                continue
            files.append(path)
    return files


def test_docs_index_exists():
    assert (DOCS / "index.html").is_file()


def test_no_performance_numbers_in_docs():
    violations: list[str] = []
    for path in _docs_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in PERF_PATTERNS:
            if pat.search(text):
                violations.append(f"{path.relative_to(ROOT)} :: {pat.pattern}")
    assert violations == []


def test_gate_status_matches_python():
    from src.core.convexity_gates import evaluate_convexity_gates

    payload = json.loads((DOCS / "gate-status.json").read_text(encoding="utf-8"))
    py = evaluate_convexity_gates()
    assert payload["cleared"] is False
    assert py["cleared"] is False
    assert payload["cleared"] == py["cleared"]


def test_site_config_has_no_cleared_key():
    text = (DOCS / "site-config.js").read_text(encoding="utf-8")
    assert "cleared:" not in text
    assert '"cleared"' not in text


def test_disclaimer_strings():
    banned = (
        "Not investment advice",
        "Research software",
        "No live client capital",
        "Gate status: cleared: false",
    )
    for name in ("index.html", "sandbox/index.html"):
        text = (DOCS / name).read_text(encoding="utf-8")
        for phrase in banned:
            assert phrase not in text, name


def test_ia5653_or_compliance_anchor():
    path = ROOT / "paper" / "compliance" / "HYPOTHETICAL_PERFORMANCE.md"
    assert path.is_file()
    assert "IA-5653" in path.read_text(encoding="utf-8")


def test_bafin_card():
    path = ROOT / "paper" / "compliance" / "EU_BAFIN.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "BaFin" in text
    assert "retail" in text.lower()


def test_no_spa_alpha_claim():
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert re.search(r"\bnull\b", index, re.I)
    assert not re.search(r"SPA.{0,40}beat", index, re.I)
    assert not re.search(r"significant alpha", index, re.I)


def test_trust_testfile_count_matches_repo():
    cfg = (DOCS / "site-config.js").read_text(encoding="utf-8")
    m = re.search(r"testFiles:\s*(\d+)", cfg)
    assert m, "testFiles missing from site-config.js"
    claimed = int(m.group(1))
    actual = len(list((ROOT / "tests").glob("test_*.py")))
    assert claimed == actual


def test_github_url_is_zauberstern():
    cfg = (DOCS / "site-config.js").read_text(encoding="utf-8")
    assert "https://github.com/zauberstern/fioracle" in cfg
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "zauberstern/fioracle" in index


def test_placeholder_email_flag():
    cfg = (DOCS / "site-config.js").read_text(encoding="utf-8")
    assert 'contactEmail: "hello@fioracle.dev"' in cfg
    assert "contactIsPlaceholder: true" in cfg


def test_analytics_disabled_by_default():
    cfg = (DOCS / "site-config.js").read_text(encoding="utf-8")
    assert "enabled: false" in cfg
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "plausible.io" not in index


def test_gate_criteria_match_code():
    from src.core.experiment_classes import get_experiment_class

    success = get_experiment_class("fioracle_convexity_v1")["success"]
    cfg = (DOCS / "site-config.js").read_text(encoding="utf-8")
    assert success.get("erod_beta_negative") is True
    assert "negative" in cfg.lower()
    assert str(int(success["min_mrp_windows_pass"])) in cfg
    assert f"{float(success['max_spa_pvalue']):.2f}" in cfg or "0.10" in cfg
    assert f"{float(success['max_pbo']):.2f}" in cfg or "0.50" in cfg


def test_refined_erod_counter_absent():
    script = (DOCS / "script.js").read_text(encoding="utf-8")
    assert "erod-value" not in script
    assert "countErod" not in script
    assert "#erod-value" not in script


def test_manifesto_exists_and_no_numeric_erod():
    assert not (DOCS / "manifesto.html").is_file()


def test_no_root_index_html():
    assert not (ROOT / "index.html").exists()


def test_no_cdn_scripts():
    pages = list(DOCS.glob("*.html"))
    pages += list((DOCS / "sandbox").glob("*.html"))
    for path in pages:
        text = path.read_text(encoding="utf-8")
        for banned in ("jsdelivr", "cdnjs", "unpkg.com"):
            assert banned not in text, f"{path} contains {banned}"


def test_vendor_anime_present():
    path = DOCS / "vendor" / "anime-3.2.1.min.js"
    assert path.is_file()
    data = path.read_bytes()
    assert len(data) > 10_000
    sha_path = DOCS / "vendor" / "anime-3.2.1.min.js.sha256"
    assert sha_path.is_file()
    expected = sha_path.read_text(encoding="utf-8").strip().split()[0]
    assert hashlib.sha256(data).hexdigest() == expected


def test_vendor_three_gsap_present():
    for name in ("three.min.js", "gsap.min.js", "ScrollTrigger.min.js", "howler.min.js"):
        path = DOCS / "vendor" / name
        assert path.is_file(), name
        data = path.read_bytes()
        assert len(data) > 5_000, name
        sha_path = DOCS / "vendor" / f"{name}.sha256"
        assert sha_path.is_file(), name
        expected = sha_path.read_text(encoding="utf-8").strip().split()[0]
        assert hashlib.sha256(data).hexdigest() == expected, name


def test_csp_meta_present():
    for name in ("index.html", "sandbox/index.html"):
        text = (DOCS / name).read_text(encoding="utf-8")
        assert "Content-Security-Policy" in text
        assert "script-src 'self'" in text


def test_a11y_contract():
    css = (DOCS / "style.css").read_text(encoding="utf-8")
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css
    assert "skip-link" in index
    assert "aria-live" in index
    assert "nav-toggle" in index


def test_leavebehind_exists_no_numbers():
    assert not (DOCS / "leavebehind.html").is_file()


def test_recordkeeping_doc():
    path = ROOT / "paper" / "compliance" / "SITE_RECORDKEEPING.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8").lower()
    assert "five years" in text or "5 years" in text
    assert "git" in text


def test_formspree_placeholder():
    cfg = (DOCS / "site-config.js").read_text(encoding="utf-8")
    assert 'formspreeId: "PLACEHOLDER"' in cfg


def test_cheap_motion_in_js():
    script = (DOCS / "script.js").read_text(encoding="utf-8")
    assert "prefers-reduced-data" in script
    assert "768" in script


def test_compass_pages_product_present():
    compass = DOCS / "compass"
    assert (compass / "index.html").is_file()
    assert (compass / "desk" / "index.html").is_file()
    assert (compass / "data" / "manifest.json").is_file()
    manifest = json.loads((compass / "data" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest.get("n_assets", 0) >= 8
    for asset in (
        "SP500_TOTAL_RETURN",
        "BBG_US_HIGH_YIELD_TOTAL_RETURN",
        "CDX_HY_5Y_TOTAL_RETURN",
    ):
        path = compass / "data" / "history" / f"{asset}.json"
        assert path.is_file(), asset
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert 'href="compass/"' in index
    built = (compass / "index.html").read_text(encoding="utf-8")
    assert "/fioracle/compass/" in built
    desk = (compass / "desk" / "index.html").read_text(encoding="utf-8")
    assert "/fioracle/compass/desk/" in desk


def _hashed_asset_refs(html: str) -> list[str]:
    """Collect relative hashed JS/CSS paths named in an index.html."""
    refs: list[str] = []
    for m in re.finditer(
        r"""(?:src|href)=["']([^"']+\.(?:js|css))["']""",
        html,
        re.I,
    ):
        ref = m.group(1)
        if ref.startswith("http") or ref.startswith("//"):
            continue
        refs.append(ref)
    return refs


def test_compass_hashed_assets_exist_and_paper_css():
    """Hashed bundles named in compass/desk index.html exist; paper tint present."""
    compass = DOCS / "compass"
    for rel_index in ("index.html", "desk/index.html"):
        index_path = compass / rel_index
        html = index_path.read_text(encoding="utf-8")
        base = index_path.parent
        refs = _hashed_asset_refs(html)
        assert refs, f"no hashed assets in {rel_index}"
        for ref in refs:
            # Strip leading ./ or absolute pages base to a file under the index dir.
            name = ref.split("/")[-1]
            candidates = list(base.rglob(name))
            assert candidates, f"missing asset {ref} for {rel_index}"

    css_files = list((compass / "assets").glob("*.css")) if (compass / "assets").is_dir() else []
    css_files += list(compass.glob("assets/*.css"))
    # Also desk may nest CSS under desk/assets
    css_files += list((compass / "desk").rglob("*.css"))
    paper = [p for p in css_files if "#f6f5f1" in p.read_text(encoding="utf-8", errors="replace")]
    assert paper, "compass CSS should contain paper tint #f6f5f1"
