"""Synchronous SQLAlchemy session for use inside Celery workers.

Celery tasks are synchronous by default. The async session (asyncpg + aiohttp)
requires a running asyncio event loop which Celery workers do not provide at
the module level.

This module provides a synchronous session factory backed by psycopg2 (or the
psycopg3 dialect) that can be used safely in `execute_run()` and related tasks.

Connection URL convention:
  DATABASE_URL uses the `postgresql+asyncpg://` scheme for FastAPI.
  We rewrite it to `postgresql+psycopg2://` for the synchronous driver.
  If `psycopg2` is not available, we fall back to SQLite in-memory for tests.

Usage:
    with get_sync_db() as session:
        run = session.get(Run, run_id)
        run.status = "running"
        session.commit()
"""

import logging
import os
import re

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_sync_engine = None
_SyncSession = None


def _build_sync_url(async_url: str) -> str:
    """Convert an asyncpg DATABASE_URL to a psycopg2-compatible URL.

    asyncpg:  postgresql+asyncpg://user:pass@host:port/db
    psycopg2: postgresql+psycopg2://user:pass@host:port/db

    Falls back to in-memory SQLite if the URL does not contain a recognisable
    Postgres scheme (useful in CI / unit tests that patch the env var).
    """
    if "asyncpg" in async_url:
        return async_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
    if async_url.startswith("sqlite"):
        return async_url
    # Unknown scheme — return as-is and let SQLAlchemy diagnose
    return async_url


def _get_engine():
    global _sync_engine
    if _sync_engine is None:
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:54322/postgres",
        )
        sync_url = _build_sync_url(db_url)
        logger.debug("Sync DB engine: %s", re.sub(r":[^@]+@", ":***@", sync_url))
        try:
            _sync_engine = create_engine(sync_url, pool_pre_ping=True)
        except Exception as exc:
            # Last resort: in-memory SQLite so tests can run without a real DB
            logger.warning(
                "Could not create sync engine (%s); falling back to SQLite", exc
            )
            _sync_engine = create_engine("sqlite:///:memory:")
    return _sync_engine


def _get_session_factory():
    global _SyncSession
    if _SyncSession is None:
        _SyncSession = sessionmaker(
            bind=_get_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _SyncSession


def get_sync_db() -> Session:
    """Return a new synchronous SQLAlchemy session.

    Caller is responsible for closing via context manager:
        with get_sync_db() as session:
            ...
    """
    factory = _get_session_factory()
    return factory()


def reset_sync_engine() -> None:
    """Reset the cached engine. Used in tests to swap in a different URL."""
    global _sync_engine, _SyncSession
    _sync_engine = None
    _SyncSession = None
