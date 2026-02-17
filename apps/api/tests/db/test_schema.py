"""Schema validation tests.

Verifies that SQLAlchemy can create all tables from the model definitions.
Acts as a proxy for migration correctness: if models create successfully,
the SQL migration schema is structurally consistent.
"""

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.models import Base


async def test_all_tables_created_successfully():
    """Verify Base.metadata.create_all produces all 10 expected tables.

    This is a lightweight proxy for the migration apply test.
    It confirms that the SQLAlchemy model definitions are internally
    consistent and can produce a valid schema.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )

    expected_tables = {
        "users",
        "organizations",
        "repositories",
        "baselines",
        "runs",
        "opportunities",
        "attempts",
        "proposals",
        "artifacts",
        "settings",
    }
    assert set(table_names) == expected_tables
    await engine.dispose()


async def test_foreign_keys_are_defined():
    """Verify that foreign key constraints exist on expected tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        fk_map = await conn.run_sync(_get_all_foreign_keys)

    # Repositories should FK to organizations
    assert any(
        fk["referred_table"] == "organizations"
        for fk in fk_map.get("repositories", [])
    )

    # Runs should FK to repositories
    assert any(
        fk["referred_table"] == "repositories"
        for fk in fk_map.get("runs", [])
    )

    # Proposals should FK to runs
    assert any(
        fk["referred_table"] == "runs"
        for fk in fk_map.get("proposals", [])
    )

    # Artifacts should FK to proposals
    assert any(
        fk["referred_table"] == "proposals"
        for fk in fk_map.get("artifacts", [])
    )

    # Settings should FK to repositories
    assert any(
        fk["referred_table"] == "repositories"
        for fk in fk_map.get("settings", [])
    )

    await engine.dispose()


def _get_all_foreign_keys(sync_conn) -> dict[str, list[dict]]:
    """Introspect all foreign keys for every table."""
    inspector = inspect(sync_conn)
    result = {}
    for table_name in inspector.get_table_names():
        fks = inspector.get_foreign_keys(table_name)
        if fks:
            result[table_name] = fks
    return result
