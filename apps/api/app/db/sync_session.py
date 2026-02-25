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


def _build_sync_url(url: str) -> str:
    """Convert any Postgres URL variant to a psycopg2-compatible URL.

    Accepted input formats
    ──────────────────────
    • postgresql+asyncpg://...  (set by FastAPI config after normalisation)
    • postgresql://...          (Supabase cloud / Railway plugin raw value)
    • postgres://...            (legacy Heroku-style alias)
    • sqlite://...              (used in tests)

    All Postgres variants are rewritten to ``postgresql+psycopg2://``.
    SQLite URLs are returned unchanged for test compatibility.
    """
    if url.startswith("sqlite"):
        return url
    # Strip any existing driver suffix so we can set psycopg2 uniformly
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://",
                   "postgresql://", "postgres://"):
        if url.startswith(prefix):
            rest = url[len(prefix):]
            return f"postgresql+psycopg2://{rest}"
    # Unknown scheme — return as-is and let SQLAlchemy diagnose
    return url


def _get_engine():
    global _sync_engine
    if _sync_engine is None:
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:54322/postgres",
        )
        sync_url = _build_sync_url(db_url)
        redacted = re.sub(r":[^@]+@", ":***@", sync_url)
        logger.info("Creating sync DB engine: %s", redacted)

        is_sqlite = sync_url.startswith("sqlite")

        # SQLite (tests only) — create without a connectivity check.
        if is_sqlite:
            _sync_engine = create_engine(sync_url)
            return _sync_engine

        # PostgreSQL (production) — retry up to 3 times with a generous timeout
        # before raising.  Never fall back to SQLite in production: a silent
        # empty-database fallback causes every task to fail with "no such table"
        # while appearing healthy, which is far harder to debug than a hard crash.
        #
        # sslmode=require is mandatory for Supabase (and most cloud Postgres
        # providers).  asyncpg enables SSL by default; psycopg2 defaults to
        # sslmode=prefer and will silently attempt a non-SSL handshake first.
        # When the server drops that non-SSL attempt (Supabase pooler does),
        # psycopg2 stalls until connect_timeout expires instead of retrying
        # with SSL — producing a 30-second hang that looks like a network
        # outage.  Forcing sslmode=require skips the plaintext attempt entirely.
        is_localhost = any(
            h in sync_url
            for h in ("localhost", "127.0.0.1", "::1", "@db:", "54322")
        )
        connect_args: dict = {"connect_timeout": 30}
        if not is_localhost:
            connect_args["sslmode"] = "require"

        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                engine = create_engine(
                    sync_url,
                    pool_pre_ping=True,
                    pool_size=2,
                    max_overflow=3,
                    pool_timeout=30,
                    connect_args=connect_args,
                )
                with engine.connect() as conn:
                    conn.execute(__import__("sqlalchemy").text("SELECT 1"))
                logger.info("Sync DB engine connected successfully (attempt %d)", attempt)
                _sync_engine = engine
                return _sync_engine
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Sync DB connection attempt %d/3 failed: %s", attempt, exc
                )

        # All retries exhausted — raise so the worker/task fails loudly instead
        # of operating against a phantom in-memory database.
        raise RuntimeError(
            f"Could not connect to the database after 3 attempts. "
            f"Check DATABASE_URL and network connectivity. Last error: {last_exc}"
        ) from last_exc

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
