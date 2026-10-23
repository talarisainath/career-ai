"""Parity tests against outputs captured from recommendation-engine.js.

`fixtures/parity_cases.json` was produced by running the real JavaScript engine
in a browser for seven profiles and recording every ranked match. These tests
assert that the Python port is byte-for-byte equivalent on user-visible data:
scores, components, matched/missing skills, explanations, ordering, and ranks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.catalog import careers as catalog_careers
from app.services.recommender import recommend

FIXTURE_FILE = Path(__file__).resolve().parent / "fixtures" / "parity_cases.json"
CASES = json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))["cases"]
CASE_IDS = [case["name"] for case in CASES]


def assert_equivalent(python_result: dict, js_case: dict) -> None:
    assert python_result["status"] == js_case["status"]
    assert [match["id"] for match in python_result["matches"]] == js_case["order"]

    if js_case["status"] != "ok":
        assert python_result["matches"] == []
        assert python_result["message"] == js_case["message"]
        return

    assert python_result["topN"] == js_case["topN"]
    assert python_result["coverage"] == js_case["coverage"]
    assert len(python_result["matches"]) == len(js_case["matches"])

    for python_match, js_match in zip(python_result["matches"], js_case["matches"]):
        assert python_match["id"] == js_match["id"]
        assert python_match["rank"] == js_match["rank"]
        assert python_match["title"] == js_match["title"]
        assert python_match["category"] == js_match["category"]
        assert python_match["shortDescription"] == js_match["shortDescription"]
        assert python_match["score"] == js_match["score"]
        assert python_match["components"] == js_match["components"]
        assert python_match["matchedSkills"] == js_match["matchedSkills"]
        assert python_match["matchedInterests"] == js_match["matchedInterests"]
        assert python_match["skillGaps"] == js_match["skillGaps"]
        assert python_match["reasons"] == js_match["reasons"]

        assert set(python_match["weightsUsed"]) == set(js_match["weightsUsed"])
        for key, value in js_match["weightsUsed"].items():
            assert python_match["weightsUsed"][key] == pytest.approx(
                value, rel=1e-12, abs=1e-12
            )


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_python_engine_matches_javascript_engine(case):
    result = recommend(case["profile"], catalog_careers())
    assert_equivalent(result, case)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_api_matches_javascript_engine(client, case):
    response = client.post("/api/recommendations", json=case["profile"])
    assert response.status_code == 200
    body = response.json()
    body.setdefault("message", None)
    assert_equivalent(body, case)


def test_fixture_set_covers_distinct_behaviours(parity_cases):
    names = {case["name"] for case in parity_cases}
    assert {
        "verified_53",
        "design_focus",
        "engineering_focus",
        "partial_skills_interests",
        "business_focus",
        "insufficient",
    } <= names
    partial = next(c for c in parity_cases if c["name"] == "partial_skills_interests")
    assert partial["coverage"] == 65
    insufficient = next(c for c in parity_cases if c["name"] == "insufficient")
    assert insufficient["status"] == "insufficient"
