"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Career
from ..schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut, summary="Service health")
def health(db: Session = Depends(get_db)) -> HealthOut:
    return HealthOut(
        status="ok",
        service="career-ai-api",
        version="1.0.0",
        careers=db.query(Career).count(),
    )
