"""Idempotent database seeding from the canonical catalog.

Running the seeder repeatedly only inserts missing careers and updates records
whose content changed; it never duplicates rows.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .catalog import careers as catalog_careers
from .models import Career

# camelCase catalog field -> model attribute
FIELD_MAP = {
    "title": "title",
    "category": "category",
    "shortDescription": "short_description",
    "overview": "overview",
    "responsibilities": "responsibilities",
    "coreSkills": "core_skills",
    "interests": "interests",
    "educationPathways": "education_pathways",
    "subjects": "subjects",
    "subjectWeights": "subject_weights",
    "beginnerProjects": "beginner_projects",
    "skillsToLearn": "skills_to_learn",
    "resources": "resources",
    "workStyles": "work_styles",
    "educationNote": "education_note",
}


def values_for(record: dict[str, Any], index: int) -> dict[str, Any]:
    values: dict[str, Any] = {"sort_order": index}
    for source, target in FIELD_MAP.items():
        values[target] = record[source]
    return values


def seed(db: Session) -> dict[str, int]:
    """Insert or refresh every catalog career. Returns counters for logging."""
    created = updated = unchanged = 0

    for index, record in enumerate(catalog_careers()):
        existing = db.get(Career, record["id"])
        values = values_for(record, index)

        if existing is None:
            db.add(Career(id=record["id"], **values))
            created += 1
            continue

        changed = False
        for attribute, value in values.items():
            if getattr(existing, attribute) != value:
                setattr(existing, attribute, value)
                changed = True
        if changed:
            updated += 1
        else:
            unchanged += 1

    db.commit()
    return {"created": created, "updated": updated, "unchanged": unchanged}
