"""Tests for the async run service helpers.

Tests the async transition and enqueue helpers used by FastAPI routes.
Uses the in-memory SQLite database from conftest.
"""

import uuid

import pytest
from sqlalchemy import select

from app.db.models import Run
from app.runs.service import async_transition_run, validate_transition
from tests.conftest import STUB_REPO_ID


class TestAsyncTransitionRun:
    """Test async_transition_run with the in-memory DB."""

    async def test_transition_queued_to_running(self, seeded_db):
        """Valid transition updates the run status in the DB."""
        run = Run(repo_id=STUB_REPO_ID, sha="abc123", status="queued")
        seeded_db.add(run)
        await seeded_db.flush()

        updated_run = await async_transition_run(seeded_db, run.id, "running")

        assert updated_run.status == "running"

    async def test_transition_running_to_completed(self, seeded_db):
        run = Run(repo_id=STUB_REPO_ID, sha="abc123", status="running")
        seeded_db.add(run)
        await seeded_db.flush()

        updated_run = await async_transition_run(seeded_db, run.id, "completed")

        assert updated_run.status == "completed"

    async def test_transition_running_to_failed(self, seeded_db):
        run = Run(repo_id=STUB_REPO_ID, sha="abc123", status="running")
        seeded_db.add(run)
        await seeded_db.flush()

        updated_run = await async_transition_run(seeded_db, run.id, "failed")

        assert updated_run.status == "failed"

    async def test_invalid_transition_raises(self, seeded_db):
        """Skipping states is not allowed."""
        run = Run(repo_id=STUB_REPO_ID, sha="abc123", status="queued")
        seeded_db.add(run)
        await seeded_db.flush()

        with pytest.raises(ValueError, match="Invalid run state transition"):
            await async_transition_run(seeded_db, run.id, "completed")

    async def test_transition_nonexistent_run_raises(self, seeded_db):
        with pytest.raises(ValueError, match="not found"):
            await async_transition_run(seeded_db, uuid.uuid4(), "running")

    async def test_transition_persists_to_db(self, seeded_db):
        """Status change is visible after flush."""
        run = Run(repo_id=STUB_REPO_ID, sha="abc123", status="queued")
        seeded_db.add(run)
        await seeded_db.flush()

        await async_transition_run(seeded_db, run.id, "running")
        await seeded_db.flush()

        result = await seeded_db.execute(select(Run).where(Run.id == run.id))
        refreshed = result.scalar_one()
        assert refreshed.status == "running"


class TestRunServiceSync:
    """Test the synchronous RunService used by Celery tasks."""

    def test_service_instantiation(self):
        """RunService can be created without any arguments."""
        from app.runs.service import RunService
        service = RunService()
        assert service is not None

    def test_execute_baseline_returns_dict(self):
        from app.runs.service import RunService
        service = RunService()
        result = service.execute_baseline("test-run-id")
        assert isinstance(result, dict)
        assert result["baseline_completed"] is True
        assert result["run_id"] == "test-run-id"
        assert "timestamp" in result
