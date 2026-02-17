"""Integration tests for the run enqueue flow.

Tests that the POST /repos/{repo_id}/run endpoint creates a run record
and attempts to dispatch a Celery task. The Celery broker is mocked
since there's no Redis in the test environment.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import STUB_REPO_ID


class TestEnqueueRunWithCelery:
    """Verify the endpoint dispatches a Celery task after creating the run."""

    @patch("app.engine.tasks.execute_run.delay")
    async def test_enqueue_dispatches_celery_task(
        self, mock_delay, seeded_client
    ):
        """A successful enqueue should call execute_run.delay()."""
        mock_task = MagicMock()
        mock_task.id = "celery-task-123"
        mock_delay.return_value = mock_task

        response = await seeded_client.post(
            f"/repos/{STUB_REPO_ID}/run",
            json={"sha": "abc123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"

        # Verify Celery task was dispatched with the run's UUID
        mock_delay.assert_called_once()
        call_args = mock_delay.call_args[0]
        assert isinstance(call_args[0], str)

    @patch("app.engine.tasks.execute_run.delay")
    async def test_enqueue_succeeds_even_if_celery_unavailable(
        self, mock_delay, seeded_client
    ):
        """If Celery is down, the run is still created with status 'queued'.

        A sweep job (future phase) handles orphaned queued runs.
        This is a critical resilience requirement — API availability
        must not depend on the Celery broker being reachable.
        """
        mock_delay.side_effect = ConnectionError("Redis unavailable")

        response = await seeded_client.post(
            f"/repos/{STUB_REPO_ID}/run",
            json={"sha": "resilience-test"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"
        assert data["sha"] == "resilience-test"

    @patch("app.engine.tasks.execute_run.delay")
    async def test_enqueue_run_appears_in_list(
        self, mock_delay, seeded_client
    ):
        """Enqueued run should be visible when listing runs."""
        mock_task = MagicMock()
        mock_task.id = "celery-task-456"
        mock_delay.return_value = mock_task

        await seeded_client.post(
            f"/repos/{STUB_REPO_ID}/run",
            json={"sha": "list-test"},
        )

        response = await seeded_client.get(f"/repos/{STUB_REPO_ID}/runs")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert any(r["sha"] == "list-test" for r in data["runs"])
