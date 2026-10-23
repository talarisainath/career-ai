"""Shared pytest configuration.

The test database is created in a temporary directory *before* the application
modules are imported, so the module-level SQLAlchemy engine points at it.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

TEMP_DIR = Path(tempfile.mkdtemp(prefix="careerai-tests-"))
os.environ["CAREERAI_DATABASE_URL"] = "sqlite:///" + (TEMP_DIR / "test.db").as_posix()
os.environ["CAREERAI_CORS_ORIGINS"] = "http://127.0.0.1:5500,http://localhost:5500"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.database as database  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

FIXTURE_FILE = Path(__file__).resolve().parent / "fixtures" / "parity_cases.json"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session():
    database.init_db()
    with database.SessionLocal() as session:
        seed(session)
        yield session


@pytest.fixture(scope="session")
def parity_cases():
    with FIXTURE_FILE.open(encoding="utf-8") as handle:
        return json.load(handle)["cases"]


@pytest.fixture()
def full_profile():
    """Profile whose Software Developer components are 15 / 67 / 76 / 100."""
    return {
        "name": "Test Student",
        "education": "bachelor",
        "branch": "computer-science",
        "percent": 85,
        "country": "India",
        "skills": {"programming": 3, "design": 4, "writing": 4},
        "interests": ["technology", "ai", "design"],
        "subjects": {"mathematics": 80, "computer-science": 70, "english": 85},
        "workStyles": ["technical"],
    }


@pytest.fixture()
def design_profile():
    return {
        "name": "",
        "education": "bachelor",
        "branch": "arts",
        "percent": 88,
        "country": "",
        "skills": {"design": 5, "creativity": 5, "communication": 4, "writing": 3},
        "interests": ["design", "media", "technology"],
        "subjects": {"english": 92, "computer-science": 78},
        "workStyles": ["creative", "people"],
    }


@pytest.fixture()
def engineering_profile():
    return {
        "name": "",
        "education": "bachelor",
        "branch": "computer-science",
        "percent": 91,
        "country": "",
        "skills": {"programming": 5, "mathematics": 5, "problem-solving": 4, "electronics": 3},
        "interests": ["technology", "ai", "electronics"],
        "subjects": {"mathematics": 92, "science": 88, "computer-science": 90},
        "workStyles": ["technical", "research"],
    }
