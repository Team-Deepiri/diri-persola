"""
Shared pytest fixtures for the Persola test suite.

DATABASE_URL is set to a SQLite in-memory URL *before* any persola imports so
that persola.db.database does not raise RuntimeError at import time.
Integration/unit tests use SQLite + aiosqlite; e2e tests expect a real
PostgreSQL instance (see DATABASE_URL env override in the e2e conftest).
"""

import os

# Must be set before any persola module is imported.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from persola.models import AgentConfig, PersonaProfile


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
async def db_engine():
    """Per-test async SQLite engine with all ORM tables created."""
    from persola.db.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture()
async def db_session(db_engine):
    """Per-test AsyncSession; rolls back any un-committed state on teardown."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# HTTP client fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
async def http_client(db_session):
    """
    Async HTTP client wired to the FastAPI app with the test SQLite database.

    ASGITransport does not trigger the app's lifespan, so init_db / close_db
    are never called.  The get_db dependency is overridden to yield the
    per-test db_session.
    """
    from persola.db.database import get_db
    from persola.api.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sample-data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def persona_payload() -> dict:
    """Minimal JSON-serialisable PersonaProfile body for POST requests."""
    return {
        "name": "Test Persona",
        "description": "A persona used in tests",
        "creativity": 0.8,
        "humor": 0.3,
        "formality": 0.6,
    }


@pytest.fixture()
def agent_payload() -> dict:
    """Minimal JSON-serialisable AgentConfig body for POST requests."""
    return {
        "name": "Test Agent",
        "role": "assistant",
        "model": "llama3:8b",
        "temperature": 0.7,
        "max_tokens": 2000,
    }
