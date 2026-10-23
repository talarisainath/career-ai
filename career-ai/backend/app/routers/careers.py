"""Career directory and detail endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..catalog import label_maps
from ..database import get_db
from ..models import Career
from ..schemas import CareerList, CareerOut, RoadmapOut, RoadmapStep

router = APIRouter(prefix="/careers", tags=["careers"])


def _all_careers(db: Session) -> list[Career]:
    return list(db.query(Career).order_by(Career.sort_order).all())


def _categories(records: list[Career]) -> list[str]:
    """First appearance order, matching the frontend filter chips."""
    seen: list[str] = []
    for record in records:
        if record.category not in seen:
            seen.append(record.category)
    return seen


def _search_blob(record: Career) -> str:
    labels = label_maps()
    parts: list[str] = [
        record.title,
        record.category,
        record.short_description,
        record.overview,
    ]
    parts.extend(labels["skills"].get(skill, skill) for skill in record.core_skills)
    parts.extend(labels["interests"].get(interest, interest) for interest in record.interests)
    parts.extend(record.skills_to_learn)
    return " ".join(parts).casefold()


@router.get("", response_model=CareerList, summary="List, search, and filter careers")
def list_careers(
    search: str = Query(default="", max_length=120),
    category: str = Query(default="", max_length=120),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> CareerList:
    records = _all_careers(db)
    categories = _categories(records)

    filtered = records
    if category and category != "All":
        filtered = [record for record in filtered if record.category == category]

    query = search.strip().casefold()
    if query:
        filtered = [record for record in filtered if query in _search_blob(record)]

    total = len(filtered)
    page = filtered[offset : offset + limit]

    return CareerList(
        total=total,
        count=len(page),
        categories=categories,
        careers=[CareerOut(**record.to_dict()) for record in page],
    )


@router.get(
    "/{career_id}/roadmap",
    response_model=RoadmapOut,
    summary="Learning roadmap for one career",
)
def career_roadmap(career_id: str, db: Session = Depends(get_db)) -> RoadmapOut:
    record = db.get(Career, career_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Career not found")

    return RoadmapOut(
        careerId=record.id,
        title=record.title,
        steps=[
            RoadmapStep(step=index, title=title)
            for index, title in enumerate(record.skills_to_learn, start=1)
        ],
    )


@router.get("/{career_id}", response_model=CareerOut, summary="Full career profile")
def career_detail(career_id: str, db: Session = Depends(get_db)) -> CareerOut:
    record = db.get(Career, career_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Career not found")
    return CareerOut(**record.to_dict())
