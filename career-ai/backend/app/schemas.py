"""Pydantic request/response models for the CareerAI API."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .catalog import branch_values, education_values, valid_keys


SkillKey = Annotated[str, Field(min_length=1, max_length=64)]
InterestKey = Annotated[str, Field(min_length=1, max_length=64)]
WorkStyleKey = Annotated[str, Field(min_length=1, max_length=64)]
SubjectKey = Annotated[str, Field(min_length=1, max_length=64)]
Proficiency = Annotated[int, Field(ge=1, le=5)]
Mark = Annotated[float, Field(ge=0, le=100)]


class AssessmentProfile(BaseModel):
    """The real five-step assessment payload produced by script.js.

    Personal identifiers are accepted only so the request matches the browser
    contract; they are never persisted (the API is stateless).
    """

    model_config = {"extra": "forbid"}

    name: str = Field(default="", max_length=80)
    education: str = Field(min_length=1, max_length=40)
    branch: str = Field(min_length=1, max_length=40)
    percent: Optional[float] = Field(default=None, ge=0, le=100)
    country: str = Field(default="", max_length=80)

    skills: Dict[SkillKey, Proficiency] = Field(default_factory=dict)
    interests: List[InterestKey] = Field(default_factory=list, max_length=64)
    subjects: Dict[SubjectKey, Mark] = Field(default_factory=dict)
    workStyles: List[WorkStyleKey] = Field(default_factory=list, max_length=32)

    @field_validator("name", "country")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("education")
    @classmethod
    def _known_education(cls, value: str) -> str:
        if value not in education_values():
            allowed = ", ".join(sorted(education_values()))
            raise ValueError(f"Unknown education level {value!r}. Expected one of: {allowed}")
        return value

    @field_validator("branch")
    @classmethod
    def _known_branch(cls, value: str) -> str:
        if value not in branch_values():
            allowed = ", ".join(sorted(branch_values()))
            raise ValueError(f"Unknown branch {value!r}. Expected one of: {allowed}")
        return value

    @field_validator("skills")
    @classmethod
    def _known_skills(cls, value: Dict[str, int]) -> Dict[str, int]:
        unknown = sorted(set(value) - valid_keys()["skills"])
        if unknown:
            raise ValueError(f"Unknown skill keys: {', '.join(unknown)}")
        return value

    @field_validator("interests")
    @classmethod
    def _known_interests(cls, value: List[str]) -> List[str]:
        unknown = sorted(set(value) - valid_keys()["interests"])
        if unknown:
            raise ValueError(f"Unknown interest keys: {', '.join(unknown)}")
        if len(set(value)) != len(value):
            raise ValueError("Interests must not contain duplicates")
        return value

    @field_validator("subjects")
    @classmethod
    def _known_subjects(cls, value: Dict[str, float]) -> Dict[str, float]:
        unknown = sorted(set(value) - valid_keys()["subjects"])
        if unknown:
            raise ValueError(f"Unknown subject keys: {', '.join(unknown)}")
        return value

    @field_validator("workStyles")
    @classmethod
    def _known_work_styles(cls, value: List[str]) -> List[str]:
        unknown = sorted(set(value) - valid_keys()["workStyles"])
        if unknown:
            raise ValueError(f"Unknown work style keys: {', '.join(unknown)}")
        if len(set(value)) != len(value):
            raise ValueError("Work styles must not contain duplicates")
        return value


class Components(BaseModel):
    skills: Optional[int] = None
    interests: Optional[int] = None
    academics: Optional[int] = None
    preferences: Optional[int] = None


class CareerMatch(BaseModel):
    id: str
    title: str
    category: str
    shortDescription: str
    score: int
    components: Components
    weightsUsed: Dict[str, float]
    matchedSkills: List[str]
    matchedInterests: List[str]
    reasons: List[str]
    skillGaps: List[str]
    rank: int


class RecommendationResponse(BaseModel):
    status: str
    source: str
    matches: List[CareerMatch]
    topN: Optional[int] = None
    coverage: Optional[int] = None
    message: Optional[str] = None


class CareerOut(BaseModel):
    id: str
    title: str
    category: str
    shortDescription: str
    overview: str
    responsibilities: List[str]
    coreSkills: List[str]
    interests: List[str]
    educationPathways: List[str]
    subjects: List[str]
    subjectWeights: Dict[str, float]
    beginnerProjects: List[str]
    skillsToLearn: List[str]
    resources: List[Dict[str, str]]
    workStyles: List[str]
    educationNote: str


class CareerList(BaseModel):
    total: int
    count: int
    categories: List[str]
    careers: List[CareerOut]


class RoadmapStep(BaseModel):
    step: int
    title: str


class RoadmapOut(BaseModel):
    careerId: str
    title: str
    steps: List[RoadmapStep]


class HealthOut(BaseModel):
    status: str
    service: str
    version: str
    careers: int


class ErrorDetail(BaseModel):
    detail: Any
