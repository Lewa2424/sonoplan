"""Runtime configuration. Production path uses PostgreSQL via DATABASE_URL."""

from __future__ import annotations

import os


def get_database_url() -> str:
    """
    DATABASE_URL for SQLAlchemy.

    Production / compose: postgresql+psycopg://...
    Tests may override with sqlite+pysqlite:///:memory: — that is NOT the prod path.
    """
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://sonoplan:sonoplan@localhost:5432/sonoplan",
    )


def is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite:") or url.startswith("sqlite+")
