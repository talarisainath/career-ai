"""Seeding and database integrity."""

from __future__ import annotations

from sqlalchemy import inspect

from app.catalog import careers as catalog_careers
from app.database import SessionLocal, engine
from app.models import Career
from app.seed import seed


def test_database_contains_all_careers_once(db_session):
    ids = [record.id for record in db_session.query(Career).all()]
    assert len(ids) == 17
    assert len(set(ids)) == 17
    assert set(ids) == {career["id"] for career in catalog_careers()}


def test_seeding_is_idempotent(db_session):
    first = seed(db_session)
    second = seed(db_session)
    assert first == {"created": 0, "updated": 0, "unchanged": 17}
    assert second == {"created": 0, "updated": 0, "unchanged": 17}
    assert db_session.query(Career).count() == 17


def test_seeding_restores_modified_records_without_duplicating(db_session):
    record = db_session.get(Career, "software-developer")
    record.title = "Tampered Title"
    db_session.commit()

    counters = seed(db_session)
    assert counters["updated"] == 1
    assert db_session.query(Career).count() == 17
    assert db_session.get(Career, "software-developer").title == "Software Developer"


def test_database_matches_the_canonical_catalog(db_session):
    by_id = {career["id"]: career for career in catalog_careers()}
    for record in db_session.query(Career).all():
        assert record.to_dict() == by_id[record.id]


def test_only_catalog_table_exists(db_session):
    # No submissions/profiles table: assessments are not stored.
    assert set(inspect(engine).get_table_names()) == {"careers"}


def test_catalog_json_is_the_frontend_export():
    catalog = catalog_careers()
    assert len(catalog) == 17
    assert len({career["id"] for career in catalog}) == 17
    required = {
        "id", "title", "category", "shortDescription", "overview",
        "responsibilities", "coreSkills", "interests", "educationPathways",
        "subjects", "subjectWeights", "beginnerProjects", "skillsToLearn",
        "resources", "workStyles", "educationNote",
    }
    for career in catalog:
        assert required <= set(career)
        assert career["title"] and career["overview"]
