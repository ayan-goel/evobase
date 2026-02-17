"""Contract tests: SQLAlchemy models must stay in sync with Supabase migrations.

These tests prevent schema drift — the silent failure mode where the ORM
models get new columns but the SQL migrations (the source of truth for the
real Postgres instance) are never updated.

Strategy:
  1. Collect every column from the SQLAlchemy model metadata.
  2. Parse the migration SQL files with a simple regex (good enough for our
     controlled migrations; no need for a full SQL parser).
  3. Assert every model column is mentioned in at least one migration file.

This is intentionally conservative: it does not check column types or
constraints, just presence. Type mismatches are caught at runtime. The
goal is purely to flag forgotten ADD COLUMN statements.
"""

import re
from pathlib import Path

import pytest

from app.db.models import (
    Artifact,
    Attempt,
    Base,
    Baseline,
    Opportunity,
    Organization,
    Proposal,
    Repository,
    Run,
    Settings,
    User,
)

# ============================================================================
# Helpers
# ============================================================================

MIGRATIONS_DIR = (
    Path(__file__).parent.parent.parent.parent.parent  # repo root
    / "infra" / "supabase" / "migrations"
)


def _all_migration_sql() -> str:
    """Concatenate all migration files into one big string for searching."""
    sql_parts = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        sql_parts.append(path.read_text())
    return "\n".join(sql_parts)


def _model_columns(model) -> dict[str, set[str]]:
    """Return {table_name: {column_names}} from a SQLAlchemy model class."""
    table = model.__table__
    return {table.name: {col.name for col in table.columns}}


def _column_in_sql(table: str, column: str, sql: str) -> bool:
    """Check if a column is referenced in the SQL for a given table.

    Looks for:
      - CREATE TABLE <table> (... <column> ...
      - ALTER TABLE <table> ADD COLUMN ... <column>
    Case-insensitive.
    """
    sql_lower = sql.lower()
    col_lower = column.lower()
    table_lower = table.lower()

    # Pattern 1: mentioned anywhere near the table name (broad but fast)
    # We look for the column name appearing within 2000 chars of the table name
    # This handles both CREATE TABLE and ALTER TABLE patterns.
    for match in re.finditer(
        r"(?:create\s+table|alter\s+table)\s+" + re.escape(table_lower),
        sql_lower,
    ):
        window = sql_lower[match.start(): match.start() + 3000]
        if re.search(r"\b" + re.escape(col_lower) + r"\b", window):
            return True

    return False


# ============================================================================
# Tests
# ============================================================================

ALL_MODELS = [User, Organization, Repository, Baseline, Run, Opportunity, Attempt, Proposal, Artifact, Settings]

MIGRATION_SQL = _all_migration_sql()


class TestModelColumnsInMigrations:
    """Every SQLAlchemy model column must appear in at least one migration file."""

    @pytest.mark.parametrize("model", ALL_MODELS, ids=lambda m: m.__tablename__)
    def test_all_columns_present_in_migrations(self, model) -> None:
        table_name = model.__tablename__
        columns = {col.name for col in model.__table__.columns}

        missing = []
        for col in sorted(columns):
            if not _column_in_sql(table_name, col, MIGRATION_SQL):
                missing.append(col)

        assert not missing, (
            f"Table '{table_name}' has columns in the SQLAlchemy model "
            f"that are NOT in any migration file:\n  "
            + "\n  ".join(missing)
            + "\n\nAdd an ALTER TABLE … ADD COLUMN statement to a new "
            "migration file in infra/supabase/migrations/."
        )


class TestMigrationFilesExist:
    def test_migrations_directory_exists(self) -> None:
        assert MIGRATIONS_DIR.exists(), (
            f"Migrations directory not found: {MIGRATIONS_DIR}\n"
            "Create infra/supabase/migrations/ and add SQL migration files."
        )

    def test_at_least_one_migration_file(self) -> None:
        files = list(MIGRATIONS_DIR.glob("*.sql"))
        assert len(files) >= 1, "Expected at least one .sql migration file"

    def test_migration_files_are_non_empty(self) -> None:
        for path in MIGRATIONS_DIR.glob("*.sql"):
            assert path.stat().st_size > 0, f"Migration file is empty: {path.name}"

    def test_migration_filenames_are_timestamped(self) -> None:
        """Migration files should start with a timestamp prefix for ordering."""
        for path in MIGRATIONS_DIR.glob("*.sql"):
            assert re.match(r"^\d{14}", path.name), (
                f"Migration filename should start with a 14-digit timestamp "
                f"(YYYYMMDDHHMMSS): {path.name}"
            )
