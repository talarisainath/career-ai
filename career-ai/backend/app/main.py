"""CareerAI FastAPI application.

The API and the existing frontend are served from one origin. Run from the
`backend` directory:

    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

Or from the repository root (used by Render):

    uvicorn app.main:app --app-dir career-ai/backend --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import cors_origins
from .database import SessionLocal, init_db
from .routers import careers, health, recommendations
from .seed import seed

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("careerai")

# frontend assets live beside `backend/`; resolve from this file, not the cwd
FRONTEND_DIR = Path(__file__).resolve().parents[2]
FRONTEND_ASSET_SUBDIRS = frozenset({"assets"})
FRONTEND_SUFFIXES = frozenset(
    {
        ".css",
        ".gif",
        ".html",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".json",
        ".map",
        ".mjs",
        ".png",
        ".svg",
        ".ttf",
        ".txt",
        ".webmanifest",
        ".webp",
        ".woff",
        ".woff2",
    }
)
FRONTEND_MEDIA_TYPES = {
    ".css": "text/css",
    ".gif": "image/gif",
    ".html": "text/html",
    ".ico": "image/x-icon",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".js": "text/javascript",
    ".json": "application/json",
    ".mjs": "text/javascript",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ttf": "font/ttf",
    ".txt": "text/plain",
    ".webmanifest": "application/manifest+json",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


def _frontend_file(relative_path: str) -> Path:
    """Resolve an allowlisted frontend file without exposing the rest of the repo."""
    candidate = (FRONTEND_DIR / relative_path).resolve()
    try:
        relative = candidate.relative_to(FRONTEND_DIR)
    except ValueError:
        raise HTTPException(status_code=404) from None

    if not relative.parts:
        raise HTTPException(status_code=404)
    top_level = relative.parts[0]
    if top_level.startswith(".") or top_level == "backend":
        raise HTTPException(status_code=404)
    if len(relative.parts) > 1 and top_level not in FRONTEND_ASSET_SUBDIRS:
        raise HTTPException(status_code=404)
    if candidate.suffix.lower() not in FRONTEND_SUFFIXES or not candidate.is_file():
        raise HTTPException(status_code=404)

    return candidate


def _frontend_response(relative_path: str) -> FileResponse:
    path = _frontend_file(relative_path)
    media_type = FRONTEND_MEDIA_TYPES.get(path.suffix.lower())
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=0, must-revalidate"},
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        counters = seed(db)
    logger.info(
        "Catalog ready: created=%s updated=%s unchanged=%s",
        counters["created"],
        counters["updated"],
        counters["unchanged"],
    )
    yield


app = FastAPI(
    title="CareerAI API",
    version="1.0.0",
    description=(
        "Career directory, detail, roadmap, and rule-based recommendation API "
        "for the CareerAI frontend. Scores are indicative profile matches, not "
        "probabilities of career success."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(health.router, prefix="/api")
app.include_router(careers.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    """Serve the existing CareerAI homepage from the same origin as the API."""
    return _frontend_response("index.html")


@app.get("/{asset_path:path}", include_in_schema=False)
def frontend_asset(asset_path: str) -> FileResponse:
    """Serve the frontend's top-level assets (and an optional assets/ folder).

    API, OpenAPI, and Swagger routes are registered before this catch-all route.
    Anything outside the allowlist (backend source, databases, README, tests)
    returns 404 instead of being exposed.
    """
    return _frontend_response(asset_path)
