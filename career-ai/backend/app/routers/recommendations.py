"""Recommendation endpoint (stateless: nothing is stored)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Career
from ..schemas import AssessmentProfile, RecommendationResponse
from ..services.recommender import recommend

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post(
    "",
    response_model=RecommendationResponse,
    summary="Rank careers for a completed assessment",
)
def create_recommendations(
    profile: AssessmentProfile,
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    records = [
        record.to_dict()
        for record in db.query(Career).order_by(Career.sort_order).all()
    ]
    result = recommend(profile.model_dump(), records)
    return RecommendationResponse(**result)
