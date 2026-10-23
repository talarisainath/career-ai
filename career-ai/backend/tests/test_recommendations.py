"""Assessment validation, ranking behaviour, scaling, and explanations."""

from __future__ import annotations

import copy

import pytest
from sqlalchemy import inspect

from app.catalog import careers as catalog_careers
from app.database import engine
from app.services.recommender import WEIGHTS, final_score, js_round

FULL_STYLE_AVAILABILITY = {key: True for key in WEIGHTS}


def submit(client, profile):
    return client.post("/api/recommendations", json=profile)


def match_by_id(response, career_id):
    return next(match for match in response.json()["matches"] if match["id"] == career_id)


def test_verified_example_components_produce_53(client, full_profile):
    response = submit(client, full_profile)
    assert response.status_code == 200
    match = match_by_id(response, "software-developer")
    assert match["components"] == {
        "skills": 15,
        "interests": 67,
        "academics": 76,
        "preferences": 100,
    }
    assert match["score"] == 53


def test_verified_example_formula_directly():
    raw = {"skills": 0.15, "interests": 2 / 3, "academics": 0.76, "preferences": 1.0}
    expected = 0.40 * 0.15 + 0.25 * (2 / 3) + 0.20 * 0.76 + 0.15 * 1.0
    unrounded = final_score(raw, FULL_STYLE_AVAILABILITY)
    assert unrounded == pytest.approx(expected, abs=1e-12)
    assert js_round(unrounded * 100) == 53


def test_valid_submission_returns_complete_ranking(client, full_profile):
    response = submit(client, full_profile)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["source"] == "python-rule-based"
    assert body["topN"] == 5
    assert body["coverage"] == 100
    assert body["message"] is None
    assert len(body["matches"]) == 17
    assert [match["rank"] for match in body["matches"]] == list(range(1, 18))
    ids = [match["id"] for match in body["matches"]]
    assert len(set(ids)) == 17

    scores = [match["score"] for match in body["matches"]]
    assert scores == sorted(scores, reverse=True)


def test_each_match_has_consistent_skill_breakdown(client, full_profile):
    response = submit(client, full_profile)
    by_id = {career["id"]: career for career in catalog_careers()}
    for match in response.json()["matches"]:
        career = by_id[match["id"]]
        assert set(match["matchedSkills"]) | set(match["skillGaps"]) == set(career["coreSkills"])
        assert not set(match["matchedSkills"]) & set(match["skillGaps"])
        assert set(match["matchedInterests"]) <= set(career["interests"])
        assert match["reasons"]
        assert all(isinstance(reason, str) and reason for reason in match["reasons"])
        assert set(match["components"]) == {"skills", "interests", "academics", "preferences"}
        assert all(
            value is None or (isinstance(value, int) and 0 <= value <= 100)
            for value in match["components"].values()
        )


def test_insufficient_information_returns_explanation(client, full_profile):
    profile = copy.deepcopy(full_profile)
    profile["skills"] = {"programming": 4}
    profile["interests"] = []
    profile["subjects"] = {}
    profile["workStyles"] = []

    response = submit(client, profile)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient"
    assert body["matches"] == []
    assert body["coverage"] is None
    assert "at least two sections" in body["message"]


def test_empty_assessment_is_insufficient_not_an_error(client, full_profile):
    profile = copy.deepcopy(full_profile)
    profile.update({"skills": {}, "interests": [], "subjects": {}, "workStyles": []})
    response = submit(client, profile)
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient"


def test_two_sections_are_enough_to_rank(client, full_profile):
    profile = copy.deepcopy(full_profile)
    profile.update({"subjects": {}, "workStyles": []})
    response = submit(client, profile)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["coverage"] == 65
    assert len(body["matches"]) == 17


@pytest.mark.parametrize("bad_mark", [-1, 101, 150.5])
def test_invalid_subject_marks_are_rejected(client, full_profile, bad_mark):
    profile = copy.deepcopy(full_profile)
    profile["subjects"] = {"mathematics": bad_mark}
    assert submit(client, profile).status_code == 422


@pytest.mark.parametrize("bad_rating", [0, 6, -2])
def test_invalid_proficiency_ratings_are_rejected(client, full_profile, bad_rating):
    profile = copy.deepcopy(full_profile)
    profile["skills"] = {"programming": bad_rating}
    assert submit(client, profile).status_code == 422


@pytest.mark.parametrize("bad_percent", [-0.1, 100.1])
def test_invalid_overall_percentage_is_rejected(client, full_profile, bad_percent):
    profile = copy.deepcopy(full_profile)
    profile["percent"] = bad_percent
    assert submit(client, profile).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("education", "university-of-life"),
        ("branch", "space-travel"),
        ("skills", {"hacking": 4}),
        ("subjects", {"history": 80}),
        ("interests", ["gaming"]),
        ("workStyles", ["lazy"]),
    ],
)
def test_unknown_education_branch_and_keys_are_rejected(client, full_profile, field, value):
    profile = copy.deepcopy(full_profile)
    profile[field] = value
    assert submit(client, profile).status_code == 422


def test_duplicate_interests_are_rejected(client, full_profile):
    profile = copy.deepcopy(full_profile)
    profile["interests"] = ["technology", "technology"]
    assert submit(client, profile).status_code == 422


def test_duplicate_work_styles_are_rejected(client, full_profile):
    profile = copy.deepcopy(full_profile)
    profile["workStyles"] = ["technical", "technical"]
    assert submit(client, profile).status_code == 422


def test_unexpected_fields_are_rejected(client, full_profile):
    profile = copy.deepcopy(full_profile)
    profile["admin"] = True
    assert submit(client, profile).status_code == 422


def test_rankings_are_deterministic(client, full_profile):
    first = submit(client, full_profile).json()
    second = submit(client, full_profile).json()
    assert [m["id"] for m in first["matches"]] == [m["id"] for m in second["matches"]]
    assert [m["score"] for m in first["matches"]] == [m["score"] for m in second["matches"]]
    assert first["coverage"] == second["coverage"]


def test_design_profile_ranks_design_careers_highly(client, design_profile):
    response = submit(client, design_profile)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    ranks = {match["id"]: match["rank"] for match in body["matches"]}
    assert body["matches"][0]["id"] == "ui-ux-designer"
    assert ranks["ui-ux-designer"] < ranks["software-developer"]
    assert ranks["ui-ux-designer"] < ranks["financial-analyst"]
    assert ranks["ui-ux-designer"] < ranks["mechanical-engineer"]


def test_engineering_profile_ranks_technical_careers_highly(client, engineering_profile):
    response = submit(client, engineering_profile)
    assert response.status_code == 200
    body = response.json()
    top_three = {match["id"] for match in body["matches"][:3]}
    assert top_three == {
        "robotics-engineer",
        "electronics-engineer",
        "machine-learning-engineer",
    }
    ranks = {match["id"]: match["rank"] for match in body["matches"]}
    assert ranks["robotics-engineer"] < ranks["financial-analyst"]
    assert ranks["financial-analyst"] > 10


def test_profiles_produce_different_rankings(client, design_profile, engineering_profile):
    design = submit(client, design_profile).json()
    engineering = submit(client, engineering_profile).json()
    assert design["matches"][0]["id"] != engineering["matches"][0]["id"]
    assert [m["score"] for m in design["matches"]] != [
        m["score"] for m in engineering["matches"]
    ]


def test_coverage_scaling_caps_incomplete_profiles(client, full_profile):
    profile = copy.deepcopy(full_profile)
    profile.update({"subjects": {}, "workStyles": []})
    body = submit(client, profile).json()

    assert body["coverage"] == 65
    # Highest possible score with 65% coverage: 0.65 coverage scales the
    # normalised score by (0.5 + 0.5 * 0.65) = 0.825.
    ceiling = js_round(final_score(
        {"skills": 1.0, "interests": 1.0, "academics": 1.0, "preferences": 1.0},
        {"skills": True, "interests": True, "academics": False, "preferences": False},
    ) * 100)
    assert ceiling == 83
    assert all(match["score"] <= ceiling for match in body["matches"])


def test_coverage_factor_never_allows_a_perfect_incomplete_score(client, full_profile):
    profile = copy.deepcopy(full_profile)
    profile.update({"interests": [], "subjects": {}, "workStyles": ["technical"]})
    body = submit(client, profile).json()
    assert body["coverage"] == 55
    assert all(match["score"] <= 78 for match in body["matches"])


def test_explanations_and_skill_gaps_are_exact(client, full_profile):
    response = submit(client, full_profile)
    match = match_by_id(response, "software-developer")

    assert match["matchedSkills"] == ["programming"]
    assert match["matchedInterests"] == ["technology", "ai"]
    assert match["skillGaps"] == ["problem-solving", "teamwork", "communication"]
    assert match["reasons"] == [
        "Matches 1 of 4 core skills (Programming).",
        "You selected the interests Technology and Artificial intelligence, "
        "which sit at the centre of this work.",
        "Your marks in Mathematics (80%), Computer science (70%), English (85%) "
        "are relevant to this career's typical subject focus.",
        "Your preferred work style — Technical and analytical work — is central "
        "to how this role is carried out.",
        "Your academic background (Computer science / IT) relates directly to this field.",
    ]


def test_advanced_ratings_are_acknowledged_in_explanations(client, full_profile):
    profile = copy.deepcopy(full_profile)
    profile["skills"] = {"programming": 5, "problem-solving": 4, "design": 4}
    response = submit(client, profile)
    match = match_by_id(response, "software-developer")
    assert "several of which you rated as advanced" in match["reasons"][0]


def test_submissions_are_not_persisted(client, full_profile):
    assert submit(client, full_profile).status_code == 200
    assert set(inspect(engine).get_table_names()) == {"careers"}
    # Only the 17 seeded careers are stored; the request is not echoed back.
    health = client.get("/api/health").json()
    assert health["careers"] == 17
    assert "name" not in submit(client, full_profile).json()
