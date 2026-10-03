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
            # Built Bubble Compass bundles contain numeric layer values; marketing
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
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "Not investment advice" in index
    assert "Research software" in index


def test_ia5653_or_compliance_anchor():
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "IA-5653" in index or 'id="compliance"' in index


def test_bafin_card():
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "BaFin" in index
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
    path = DOCS / "manifesto.html"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "Content-Security-Policy" in text
    assert "script-src 'self'" in text
    assert "-0.42" not in text
    assert "0.42" not in text


def test_no_root_index_html():
    assert not (ROOT / "index.html").exists()


def test_no_cdn_scripts():
    for path in list(DOCS.glob("*.html")) + list((DOCS / "molecule").glob("*.html")):
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
    for name in ("index.html", "manifesto.html", "molecule/index.html"):
        text = (DOCS / name).read_text(encoding="utf-8")
        assert "Content-Security-Policy" in text
        assert "script-src 'self'" in text


def test_molecule_page_fail_closed():
    text = (DOCS / "molecule" / "index.html").read_text(encoding="utf-8")
    assert "Not investment advice" in text
    assert "unpriced" in text.lower()
    assert "cleared: false" in text
    assert "Simple Mode" in text
    assert "vendor/three.min.js" in text
    assert "vendor/gsap.min.js" in text
    assert "vendor/howler.min.js" in text
    assert "js/scenes.js" in text
    assert "jsdelivr" not in text
    assert "media-src 'self'" in text
    assert (DOCS / "molecule" / "app.js").is_file()
    css = (DOCS / "molecule" / "style.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    assert (DOCS / "molecule" / "assets" / "ambient_hum.wav").is_file()
    assert (DOCS / "data" / "network_topology.json").is_file()


def test_molecule_app_has_dual_equity_and_waterfall():
    js = (DOCS / "molecule" / "app.js").read_text(encoding="utf-8")
    assert "cum_pnl_rl" in js
    assert "cum_pnl_ri" in js
    assert "waterfall" in js
    assert "ScrollTrigger" in js
    scenes = (DOCS / "molecule" / "js" / "scenes.js").read_text(encoding="utf-8")
    assert "CatmullRomCurve3" in scenes
    assert "TubeGeometry" in scenes
    assert (DOCS / "molecule" / "js" / "orb.js").is_file()


def test_a11y_contract():
    css = (DOCS / "style.css").read_text(encoding="utf-8")
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css
    assert "skip-link" in index
    assert "aria-live" in index
    assert "nav-toggle" in index
    assert "dashed" in css
    assert "double" in css


def test_leavebehind_exists_no_numbers():
    path = DOCS / "leavebehind.html"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    for pat in PERF_PATTERNS:
        assert not pat.search(text), pat.pattern


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
