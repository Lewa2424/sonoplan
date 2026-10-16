"""SQLAlchemy engine / session. Default dialect is PostgreSQL."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sonoplan_api.config import get_database_url, is_sqlite_url


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    db_url = url if url is not None else get_database_url()
    kwargs: dict = {"future": True}
    if is_sqlite_url(db_url):
        # Test-only SQLite: one shared in-memory DB across connections/threads.
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    return create_engine(db_url, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
