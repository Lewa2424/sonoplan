"""
Pytest fixtures.

IMPORTANT: tests use SQLite in-memory via dependency override.
That is NOT the production database path — production / compose uses
PostgreSQL via DATABASE_URL (see infra/.env.example and Alembic migration).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from sonoplan_api.db import Base, get_db, make_engine
from sonoplan_api.main import app

# Ensure ORM tables are registered on Base.metadata before create_all.
import sonoplan_api.models  # noqa: F401


@pytest.fixture()
def client():
    # Test-only SQLite — explicitly marked; not a substitute for PostgreSQL in prod.
    engine = make_engine("sqlite+pysqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
