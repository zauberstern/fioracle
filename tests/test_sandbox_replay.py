"""Replay-desk math: lag, costs, and the twenty question dates."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.export_sandbox_replay import (
    HEADLINE_NOUN,
    choice_lines,
    choice_vectors,
    compound_index,
    cost_for_asset,
    explain_miss,
    format_prompt,
    format_value,
    select_question_dates,
    style_fill,
    to_bps,
)

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "docs" / "sandbox" / "data" / "replay.json"
SCHEMA = ROOT / "docs" / "sandbox" / "data" / "trees" / "US_10Y_GOV_BOND.schema.json"


def test_decision_earns_the_next_bar_and_a_held_day_is_free():
    dates = ["2008-01-01", "2008-01-02", "2008-01-03"]
    sleeves = ["A"]
    weights = pd.DataFrame(
        {"A": [0.5, 0.5, 0.5], "cash_allocation": [0.5, 0.5, 0.5]},
        index=pd.to_datetime(dates),
    )
    asset = pd.DataFrame(
        {"A": [0.0, 0.01, -0.02]},
        index=pd.to_datetime(dates),
    )
    rf = pd.Series([0.0, 0.0001, 0.0001], index=asset.index)
    costs = {"A": 0.001}
    index = compound_index(weights, asset, rf, costs, sleeves, lag=1, prev_zero=True)
    # Day 0 has no execution bar inside the frame (lag points at day 1).
    # Decision 0 earns day 1: gross 0.5*0.01 + 0.5*0.0001 - |0.5|*0.001
    net1 = 0.00505 - 0.0005
    # Decision 1 holds, so day 2 has no cost: 0.5*-0.02 + 0.5*0.0001
    net2 = -0.01 + 0.00005
    assert index.iloc[0] == pytest.approx(1.0)
    assert index.iloc[1] == pytest.approx(1.0 * (1.0 + net1))
    assert index.iloc[2] == pytest.approx(index.iloc[1] * (1.0 + net2))


def test_missing_return_with_a_weight_withholds_the_rest():
    dates = ["2008-01-01", "2008-01-02"]
    weights = pd.DataFrame(
        {"A": [0.4, 0.4], "cash_allocation": [0.6, 0.6]},
        index=pd.to_datetime(dates),
    )
    asset = pd.DataFrame({"A": [np.nan, np.nan]}, index=weights.index)
    rf = pd.Series([0.0, 0.0], index=weights.index)
    index = compound_index(weights, asset, rf, {"A": 0.0}, ["A"], lag=1, prev_zero=True)
    assert np.isnan(index.iloc[1])


def test_basis_points_sum_to_10000():
    bps = to_bps(np.array([0.3333, 0.3333, 0.3334]))
    assert sum(bps) == 10000
    assert all(v >= 0 for v in bps)


def test_cost_lookup_uses_the_longest_pattern():
    table = {"US_TIPS": 0.0003, "US_TIPS_0_5": 0.0009}
    assert cost_for_asset("US_TIPS_0_5", table, 0.0005) == 0.0009
    assert cost_for_asset("GOLD", table, 0.0005) == 0.0005


def test_selector_keeps_the_largest_distinct_moves_in_time_order():
    idx = pd.to_datetime(["2008-01-01", "2008-02-01", "2008-03-03", "2008-04-01", "2008-05-01"])
    # Row 1 and row 4 share a vector. Row 4's move is larger, so it wins the slot.
    book = pd.DataFrame(
        {
            "A": [0.2, 0.5, 0.52, 0.9, 0.5],
            "B": [0.2, 0.1, 0.08, 0.0, 0.1],
            "cash_allocation": [0.6, 0.4, 0.4, 0.1, 0.4],
        },
        index=idx,
    )
    ew = pd.DataFrame({"A": 0.5, "B": 0.5, "cash_allocation": 0.0}, index=idx)
    book_net = pd.Series([0.0, 0.02, 0.0, 0.03, 0.0], index=idx)
    bench = pd.Series(0.0, index=idx)
    picked, floor = select_question_dates(
        book, ew, book_net, bench, n=2, floor=0.02, sleeves=["A", "B"]
    )
    assert floor == 0.02
    assert [d.strftime("%Y-%m-%d") for d in picked] == ["2008-04-01", "2008-05-01"]


def test_eight_choices_and_exactly_one_matches_the_book():
    ids = ["US_10Y_GOV_BOND", "BBG_US_TREASURY", "BBG_US_CORPORATE", "BBG_US_HIGH_YIELD", "GOLD", "cash_allocation"]
    previous = np.array([0.10, 0.10, 0.10, 0.10, 0.10, 0.50])
    book = np.array([0.20, 0.05, 0.05, 0.00, 0.20, 0.50])
    mv = np.array([0.00, 0.00, 0.40, 0.10, 0.00, 0.50])
    ew = np.array([0.16, 0.16, 0.16, 0.16, 0.16, 0.20])
    choices = choice_vectors(ids, previous, book, mv, ew)
    assert len(choices) == 8
    matches = [np.max(np.abs(c - book)) < 1e-4 for c in choices]
    assert sum(matches) == 1
    for vector in choices:
        assert np.all(vector >= -1e-12)
        assert vector.sum() == pytest.approx(1.0)


def test_prompt_names_the_zscore_and_not_the_vix_index():
    text = format_prompt(
        sleeve="the 10-year Treasury",
        date="2008-09-15",
        features=[
            {"id": "avg_return_hl21", "label": "21-day average return", "value": -0.000029},
            {"id": "macro_vix_level_norm", "label": "VIX level", "value": 1.55},
            {"id": "macro_hy_oas_level_norm", "label": "High-yield spread level", "value": 1.2},
        ],
        regime="crisis",
    )
    assert "15 Sep 2008" in text
    assert "10-year Treasury" in text
    assert "crisis" in text
    assert "VIX level" not in text
    assert "HY" not in text
    assert "OAS" not in text
    assert "standard deviations" in text
    assert "percent per day" in text
    assert "\u2014" not in text
    assert format_value(19.82) == "19.8"


def test_a_miss_names_the_weight_gap_and_the_saved_probability():
    ids = ["BBG_US_HIGH_YIELD", "cash_allocation"]
    book = [1000, 9000]
    choice = [4000, 6000]
    evidence = {
        "date": "1 Feb 2008",
        "feature_sleeve": "BBG_US_HIGH_YIELD",
        "probs": [
            {
                "id": "BBG_US_HIGH_YIELD",
                "label": "high yield credit",
                "calm": 1.0,
                "inflationary": 0.0,
                "crisis": 0.0,
            }
        ],
        "importance": [
            {
                "id": "BBG_US_HIGH_YIELD",
                "feature": "macro_inflation_level",
                "plain": "the inflation rate",
                "importance": 0.340,
            }
        ],
        "inputs": [{"id": "macro_inflation_level", "text": "9.1 percent"}],
    }
    text = explain_miss(book, choice, ids, evidence, lambda name: name)
    assert "FIOracle" in text
    assert "high yield credit" in text
    assert "1.000" in text
    assert "inflation rate" in text
    assert "9.1 percent" in text
    assert "leaf" in text
    assert "HY" not in text and "OAS" not in text and "VIX level" not in text
    assert "\u2014" not in text
    assert explain_miss(book, book, ids, evidence, lambda name: name) == ""


def test_choice_lines_use_percentage_points():
    ids = ["BBG_US_HIGH_YIELD", "GOLD", "US_CASH", "cash_allocation"]
    labels = {
        "BBG_US_HIGH_YIELD": "US HY",
        "GOLD": "Gold",
        "US_CASH": "Cash",
        "cash_allocation": "Uninvested cash",
    }
    before = np.array([0.10, 0.14, 0.20, 0.56])
    after = np.array([0.40, 0.06, 0.08, 0.46])
    headline, sleeves = choice_lines(before, after, ids, labels.get)
    assert "bp" not in headline and "bp" not in sleeves
    assert "book" not in headline.lower()
    assert "high yield" in headline.lower()
    hold, rest = choice_lines(before, before, ids, labels.get)
    assert hold == "Hold these weights"
    assert rest == ""


def test_style_fills_the_gap_from_answers_so_far_and_stops():
    ids = ["A", "B", "cash_allocation"]
    book = [
        [5000, 0, 5000],
        [8000, 0, 2000],
        [6000, 2000, 2000],
        [6000, 2000, 2000],
        [1000, 7000, 2000],
        [1000, 7000, 2000],
    ]
    mv = book
    ew = [[5000, 5000, 0]] * 6
    live = [[True, True]] * 6
    answers = {
        1: {"policy": "cash", "bps": [0, 0, 10000]},
        4: {"policy": "book", "bps": [1000, 7000, 2000]},
    }
    rows = style_fill(ids, book, mv, ew, live, [1, 4], answers)
    assert rows[5] is None
    assert rows[0] == [0, 0, 10000]
    assert rows[1] == [0, 0, 10000]
    assert rows[4] == [1000, 7000, 2000]
    assert rows[2] == [3000, 1000, 6000]
    assert sum(rows[2]) == 10000
    script = ROOT / "docs" / "sandbox" / "style.js"
    node = subprocess.run(
        [
            "node",
            "-e",
            "const s=require(process.argv[1]);"
            "const ids=['A','B','cash_allocation'];"
            "const book=[[5000,0,5000],[8000,0,2000],[6000,2000,2000],[6000,2000,2000],[1000,7000,2000],[1000,7000,2000]];"
            "const live=[[true,true],[true,true],[true,true],[true,true],[true,true],[true,true]];"
            "const answers={1:{policy:'cash',bps:[0,0,10000]},4:{policy:'book',bps:[1000,7000,2000]}};"
            "process.stdout.write(JSON.stringify(s.styleFill(ids,book,book,book,live,[1,4],answers)));",
            str(script),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(node.stdout) == rows


def test_the_path_is_manual_only_when_every_question_is_off():
    script = ROOT / "docs" / "sandbox" / "style.js"
    node = subprocess.run(
        [
            "node",
            "-e",
            "const s=require(process.argv[1]);"
            "const ids=['A','B','cash_allocation'];"
            "const book=[[5000,0,5000],[8000,0,2000],[6000,2000,2000],[6000,2000,2000],[1000,7000,2000],[1000,7000,2000]];"
            "const live=[[true,true],[true,true],[true,true],[true,true],[true,true],[true,true]];"
            "const manual=s.assemblePath(ids,book,book,book,live,[1,4],{},[{day:1,bps:[0,0,10000]},{day:4,bps:[1000,0,9000]}]);"
            "const hybrid=s.assemblePath(ids,book,book,book,live,[1,4],{1:{policy:'cash',bps:[0,0,10000]},4:{policy:'book',bps:[1000,7000,2000]}},[{day:0,bps:[2500,2500,5000]},{day:2,bps:[0,1000,9000]},{day:5,bps:[5000,5000,0]}]);"
            "const unanswered=s.assemblePath(ids,book,book,book,live,[1,4],{4:{policy:'book',bps:[1000,7000,2000]}},[{day:2,bps:[0,1000,9000]}]);"
            "process.stdout.write(JSON.stringify({manual:manual,hybrid:hybrid,unanswered:unanswered}));",
            str(script),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(node.stdout)
    manual = payload["manual"]
    assert manual[0] is None
    assert manual[1] == [0, 0, 10000]
    assert manual[3] == [0, 0, 10000]
    assert manual[4] == [1000, 0, 9000]
    assert manual[5] == [1000, 0, 9000]
    hybrid = payload["hybrid"]
    assert hybrid[0] == [0, 0, 10000]
    assert hybrid[2] == [0, 1000, 9000]
    assert hybrid[3] == [3000, 1000, 6000]
    assert hybrid[4] == [1000, 7000, 2000]
    assert hybrid[5] is None
    unanswered = payload["unanswered"]
    assert unanswered[2] == [0, 0, 10000]
    assert unanswered[4] == [1000, 7000, 2000]
    assert unanswered[5] is None


def test_style_zeros_a_sleeve_that_is_not_live():
    ids = ["A", "B", "cash_allocation"]
    book = [[5000, 5000, 0]] * 3
    ew = [[5000, 5000, 0]] * 3
    live = [[True, False]] * 3
    answers = {
        0: {"policy": "ew", "bps": [5000, 0, 5000]},
        2: {"policy": "book", "bps": [10000, 0, 0]},
    }
    rows = style_fill(ids, book, book, ew, live, [0, 2], answers)
    assert rows[1][1] == 0
    assert sum(rows[1]) == 10000
    assert rows[2] == [10000, 0, 0]
    script = ROOT / "docs" / "sandbox" / "style.js"
    node = subprocess.run(
        [
            "node",
            "-e",
            "const s=require(process.argv[1]);"
            "const ids=['A','B','cash_allocation'];"
            "const book=[[5000,5000,0],[5000,5000,0],[5000,5000,0]];"
            "const live=[[true,false],[true,false],[true,false]];"
            "const answers={0:{policy:'ew',bps:[5000,0,5000]},2:{policy:'book',bps:[10000,0,0]}};"
            "process.stdout.write(JSON.stringify(s.styleFill(ids,book,book,book,live,[0,2],answers)));",
            str(script),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(node.stdout)[1][1] == 0


def _headline_matches_vector(headline, detail, before, after, ids):
    if list(before) == list(after):
        assert headline == "Hold these weights"
        assert detail == ""
        return
    assert headline != "Hold these weights"
    nouns = sorted(HEADLINE_NOUN.items(), key=lambda item: len(item[1]), reverse=True)
    for clause in headline.split(","):
        low = clause.strip().lower()
        name = next((sid for sid, noun in nouns if noun.lower() in low and sid in ids), None)
        assert name, headline
        delta = after[ids.index(name)] - before[ids.index(name)]
        if "fund from" in low or low.startswith("cut"):
            assert delta < 0, (headline, name)
        elif low.startswith("add") or low.startswith("raise"):
            assert delta > 0, (headline, name)


def test_replay_json_contract():
    assert REPLAY.is_file(), "export docs/sandbox/data/replay.json before this check"
    payload = json.loads(REPLAY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    allowed = set(schema["feature_names"])
    assert payload["execution_lag_days"] == 1
    questions = payload["questions"]
    assert len(questions) == 20
    banned = re.compile(r"\d+\.\d{2}\s*%|Sharpe ratio of|returned -|\u2014")
    blob = json.dumps(questions)
    assert banned.search(blob) is None
    sleeves = [row["id"] for row in payload["sleeves"]]
    for item in questions:
        assert len(item["choices"]) == 8
        ids = [feat["id"] for feat in item["features"]]
        assert len(ids) == len(set(ids))
        assert set(ids) == allowed
        assert "HY" not in item["prompt"]
        assert "OAS" not in item["prompt"]
        assert "VIX level" not in item["prompt"]
        assert "\u2014" not in item["prompt"]
        previous = item["previous_bps"]
        for choice in item["choices"]:
            _headline_matches_vector(choice["headline"], choice.get("sleeves") or "", previous, choice["bps"], sleeves)
        for feat in item["features"]:
            assert feat["id"] in allowed
        book = item["book_bps"]
        assert sum(book) == 10000
        matches = 0
        for choice in item["choices"]:
            assert sum(choice["bps"]) == 10000
            assert all(v >= 0 for v in choice["bps"])
            if choice["bps"] == book:
                matches += 1
            assert "policy" in choice
            headline = choice["headline"]
            assert "bp" not in headline
            assert "book" not in headline.lower()
            assert "VIX level" not in item["prompt"]
            if choice["bps"] == book:
                assert choice.get("miss", "") == ""
            else:
                note = choice["miss"]
                assert "FIOracle" in note
                assert "leaf" in note
                assert "HY" not in note and "OAS" not in note and "VIX level" not in note
                assert "\u2014" not in note
        assert matches == 1
    assert len(payload["book_bps"]) == len(payload["dates"])
    assert len(payload["mv_bps"]) == len(payload["dates"])
    assert len(payload["ew_bps"]) == len(payload["dates"])
    assert len(payload["dates"]) == len(payload["lines"]["book"])
    assert len(payload["returns"]) == len(payload["dates"])
    assert len(payload["returns"][0]) == len(sleeves) - 1
