"""SQLAlchemy engine, session factory, and declarative base."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import database_url


def _ensure_sqlite_directory(url: str) -> None:
    """Create the parent directory for a file-backed SQLite database if needed."""
    try:
        parsed = make_url(url)
    except Exception:  # pragma: no cover - invalid URLs fail clearly at connect time
        return
    if parsed.get_backend_name() != "sqlite":
        return

    database = parsed.database
    if not database or database == ":memory:" or database.startswith("file:"):
        return

    Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


URL = database_url()
_ensure_sqlite_directory(URL)

engine = create_engine(
    URL,
    connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables. Safe to call repeatedly."""
    from . import models  # noqa: F401  (register mappers before create_all)

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
