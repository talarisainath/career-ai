"""Career catalog, search/filter, detail, and roadmap endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import DATA_FILE

CATALOG = json.loads(Path(DATA_FILE).read_text(encoding="utf-8"))["careers"]
CATALOG_BY_ID = {career["id"]: career for career in CATALOG}

EXPECTED_CATEGORIES = [
    "Software & Technology",
    "Data & AI",
    "Design & Creative",
    "Engineering",
    "Science & Research",
    "Business & Finance",
    "Media & Communication",
    "Education",
]


def test_catalog_lists_all_17_careers(client):
    response = client.get("/api/careers")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 17
    assert body["count"] == 17
    assert len(body["careers"]) == 17
    assert body["categories"] == EXPECTED_CATEGORIES
    assert [career["id"] for career in body["careers"]] == [c["id"] for c in CATALOG]


def test_catalog_preserves_every_field_from_the_frontend_data(client):
    response = client.get("/api/careers")
    assert response.status_code == 200
    for career in response.json()["careers"]:
        source = CATALOG_BY_ID[career["id"]]
        assert career == source
        assert career["resources"] and all(
            set(resource) == {"label", "url"} and resource["url"].startswith("http")
            for resource in career["resources"]
        )
        assert career["coreSkills"] and career["interests"]
        assert career["subjectWeights"]
        assert career["skillsToLearn"] and career["beginnerProjects"]


def test_search_is_case_insensitive_and_matches_content(client):
    response = client.get("/api/careers", params={"search": "SOFTWARE"})
    assert response.status_code == 200
    ids = [career["id"] for career in response.json()["careers"]]
    assert "software-developer" in ids


def test_search_matches_skill_labels(client):
    # "Programming" is only a label (the stored key is "programming").
    response = client.get("/api/careers", params={"search": "Programming"})
    assert response.status_code == 200
    ids = [career["id"] for career in response.json()["careers"]]
    assert "software-developer" in ids
    assert "machine-learning-engineer" in ids

    # "Data analysis" is a label for the "data-analysis" key.
    response = client.get("/api/careers", params={"search": "Data analysis"})
    ids = [career["id"] for career in response.json()["careers"]]
    assert "data-analyst" in ids


def test_search_matches_learning_topics(client):
    response = client.get("/api/careers", params={"search": "Version control"})
    assert response.status_code == 200
    ids = [career["id"] for career in response.json()["careers"]]
    assert "software-developer" in ids


def test_category_filter_returns_exact_category(client):
    response = client.get("/api/careers", params={"category": "Data & AI"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [career["id"] for career in body["careers"]] == [
        "data-analyst",
        "machine-learning-engineer",
    ]


def test_category_and_search_can_be_combined(client):
    response = client.get(
        "/api/careers", params={"category": "Engineering", "search": "electrical"}
    )
    assert response.status_code == 200
    ids = [career["id"] for career in response.json()["careers"]]
    assert "electrical-engineer" in ids
    assert all(
        CATALOG_BY_ID[career_id]["category"] == "Engineering" for career_id in ids
    )


def test_unknown_category_returns_empty_result_set(client):
    response = client.get("/api/careers", params={"category": "Underwater Basket Weaving"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["count"] == 0
    assert body["careers"] == []


def test_all_category_alias_returns_everything(client):
    response = client.get("/api/careers", params={"category": "All"})
    assert response.status_code == 200
    assert response.json()["total"] == 17


def test_search_with_only_whitespace_returns_everything(client):
    response = client.get("/api/careers", params={"search": "   "})
    assert response.status_code == 200
    assert response.json()["total"] == 17


def test_pagination_limits_and_offsets(client):
    first = client.get("/api/careers", params={"limit": 5, "offset": 0}).json()
    assert first["total"] == 17
    assert first["count"] == 5
    assert len(first["careers"]) == 5

    last = client.get("/api/careers", params={"limit": 5, "offset": 15}).json()
    assert last["total"] == 17
    assert last["count"] == 2

    first_ids = {career["id"] for career in first["careers"]}
    last_ids = {career["id"] for career in last["careers"]}
    assert not first_ids & last_ids


def test_invalid_pagination_is_rejected(client):
    assert client.get("/api/careers", params={"limit": 0}).status_code == 422
    assert client.get("/api/careers", params={"offset": -1}).status_code == 422


def test_career_detail_returns_full_profile(client):
    response = client.get("/api/careers/software-developer")
    assert response.status_code == 200
    career = response.json()
    assert career == CATALOG_BY_ID["software-developer"]
    assert len(career["responsibilities"]) >= 3
    assert len(career["educationPathways"]) >= 2
    assert len(career["resources"]) >= 2


def test_unknown_career_returns_404(client):
    response = client.get("/api/careers/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Career not found"


def test_roadmap_reuses_stored_learning_steps(client):
    response = client.get("/api/careers/ui-ux-designer/roadmap")
    assert response.status_code == 200
    body = response.json()
    source = CATALOG_BY_ID["ui-ux-designer"]
    assert body["careerId"] == "ui-ux-designer"
    assert body["title"] == source["title"]
    assert [step["step"] for step in body["steps"]] == list(
        range(1, len(source["skillsToLearn"]) + 1)
    )
    assert [step["title"] for step in body["steps"]] == source["skillsToLearn"]


def test_roadmap_for_unknown_career_returns_404(client):
    response = client.get("/api/careers/nope/roadmap")
    assert response.status_code == 404
    assert response.json()["detail"] == "Career not found"
