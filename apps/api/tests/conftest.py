"""Shared test fixtures for the SelfOpt API test suite.

Uses an in-memory SQLite database for fast, isolated model/CRUD tests.
SQLAlchemy adapts UUID and JSON column types to SQLite-compatible equivalents.
Each test gets a fresh database for isolation.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Organization, Repository, Run, User
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
async def async_engine():
    """Create a fresh async SQLite engine for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a test DB session."""
    session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def app(async_engine):
    """Create a FastAPI app with the DB dependency overridden to use test SQLite.

    The SlowAPI rate limiter uses an in-memory storage that persists across
    requests within the same process. To isolate tests from each other, we
    reset the storage buckets on the module-level limiter before each test.
    """
    from app.core.limiter import limiter

    # Reset all in-memory rate-limit buckets so each test starts clean.
    try:
        limiter.reset()
    except Exception:
        pass  # reset() may fail if storage not initialised yet — that's fine

    test_app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        session_factory = async_sessionmaker(
            async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client wired to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Seed data helpers matching the stub auth user
# ---------------------------------------------------------------------------

STUB_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
STUB_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
STUB_REPO_ID = uuid.UUID("00000000-0000-0000-0000-000000000100")


@pytest.fixture
async def seeded_db(db_session) -> AsyncSession:
    """Seed the database with a user, org, and repo for route tests."""
    user = User(id=STUB_USER_ID, email="dev@selfopt.local")
    db_session.add(user)
    await db_session.flush()

    org = Organization(id=STUB_ORG_ID, name="Dev Organization", owner_id=user.id)
    db_session.add(org)
    await db_session.flush()

    repo = Repository(
        id=STUB_REPO_ID,
        org_id=org.id,
        github_repo_id=123456789,
        default_branch="main",
        package_manager="npm",
        install_cmd="npm install",
        build_cmd="npm run build",
        test_cmd="npm test",
    )
    db_session.add(repo)
    await db_session.commit()
    return db_session


@pytest.fixture
async def seeded_client(app, seeded_db) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with a pre-seeded database."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
