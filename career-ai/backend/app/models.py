"""Career catalog ORM model.

Structured fields use SQLAlchemy's JSON type (TEXT storage on SQLite) so the
original arrays/objects from the frontend data survive the round trip intact.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Career(Base):
    __tablename__ = "careers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    short_description: Mapped[str] = mapped_column(Text, nullable=False)
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    education_note: Mapped[str] = mapped_column(Text, nullable=False)

    responsibilities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    core_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    interests: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    education_pathways: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    subjects: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    subject_weights: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    beginner_projects: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    skills_to_learn: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    resources: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    work_styles: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialise using the frontend's camelCase field names."""
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "shortDescription": self.short_description,
            "overview": self.overview,
            "responsibilities": list(self.responsibilities),
            "coreSkills": list(self.core_skills),
            "interests": list(self.interests),
            "educationPathways": list(self.education_pathways),
            "subjects": list(self.subjects),
            "subjectWeights": dict(self.subject_weights),
            "beginnerProjects": list(self.beginner_projects),
            "skillsToLearn": list(self.skills_to_learn),
            "resources": [dict(resource) for resource in self.resources],
            "workStyles": list(self.work_styles),
            "educationNote": self.education_note,
        }
