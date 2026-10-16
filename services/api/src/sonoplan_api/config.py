"""Runtime configuration. Production path uses PostgreSQL via DATABASE_URL."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# services/api/.env wins over stale shell env (e.g. old SONOPLAN_GITHUB_TOKEN).
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)


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
