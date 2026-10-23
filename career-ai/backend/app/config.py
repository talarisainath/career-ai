"""Application configuration (environment driven, no secrets required)."""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "data" / "careers.json"

DEFAULT_DB_PATH = BACKEND_DIR / "careerai.db"
DEFAULT_CORS_ORIGINS = "http://127.0.0.1:5500,http://localhost:5500"


def database_url() -> str:
    """SQLite by default; override with CAREERAI_DATABASE_URL (e.g. for tests).

    Render's free web services have an ephemeral filesystem. When running there,
    keep the disposable SQLite cache under /tmp; startup recreates and reseeds it
    from the version-controlled catalog.
    """
    override = os.environ.get("CAREERAI_DATABASE_URL", "").strip()
    if override:
        return override
    if os.environ.get("RENDER", "").strip().lower() in {"1", "true", "yes"}:
        return "sqlite:////tmp/careerai.db"
    return "sqlite:///" + DEFAULT_DB_PATH.as_posix()


def cors_origins() -> list[str]:
    """Browser origins allowed to call the API (comma separated env override)."""
    raw = os.environ.get("CAREERAI_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    # A wildcard with credentials is invalid; this API never uses credentials.
    return origins or ["http://127.0.0.1:5500"]
