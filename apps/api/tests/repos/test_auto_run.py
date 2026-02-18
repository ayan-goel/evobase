"""Tests for the auto-run-on-connect behaviour added in Phase 3.

When a repo is connected via POST /repos/connect, the endpoint should:
1. Call create_and_enqueue_run to create a Run row.
2. Return the run ID in the response as `initial_run_id`.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run
from tests.conftest import STUB_ORG_ID

_PATCH = "app.repos.router.create_and_enqueue_run"
_FIXED_RUN_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")


def _fake_run() -> MagicMock:
    """A lightweight stand-in for a Run ORM instance.

    We use MagicMock rather than a real Run() because the real ORM object
    would need to be flushed/refreshed against a real DB session. The router
    only reads `run.id` from this object, so the mock is sufficient.
    """
    m = MagicMock(spec=Run)
    m.id = _FIXED_RUN_ID
    return m


class TestAutoRunOnConnect:
    @patch(_PATCH, new_callable=AsyncMock)
    async def test_connect_repo_auto_enqueues_run(
        self,
        mock_enqueue: AsyncMock,
        seeded_client: AsyncClient,
    ) -> None:
        """create_and_enqueue_run must be called exactly once per connect."""
        mock_enqueue.return_value = _fake_run()

        res = await seeded_client.post(
            "/repos/connect",
            json={"github_repo_id": 7770001, "org_id": str(STUB_ORG_ID)},
        )
        assert res.status_code == 201
        mock_enqueue.assert_called_once()

    @patch(_PATCH, new_callable=AsyncMock)
    async def test_connect_repo_run_has_correct_repo_id(
        self,
        mock_enqueue: AsyncMock,
        seeded_client: AsyncClient,
    ) -> None:
        """create_and_enqueue_run is called with the newly-created repo's ID."""
        mock_enqueue.return_value = _fake_run()

        res = await seeded_client.post(
            "/repos/connect",
            json={"github_repo_id": 7770002, "org_id": str(STUB_ORG_ID)},
        )
        assert res.status_code == 201
        repo_id = res.json()["id"]

        # Second positional arg to create_and_enqueue_run(db, repo_id, ...) is repo_id
        called_repo_id = mock_enqueue.call_args.args[1]
        assert str(called_repo_id) == repo_id

    @patch(_PATCH, new_callable=AsyncMock)
    async def test_connect_repo_returns_run_id(
        self,
        mock_enqueue: AsyncMock,
        seeded_client: AsyncClient,
    ) -> None:
        """Response body must include initial_run_id matching the created run."""
        mock_enqueue.return_value = _fake_run()

        res = await seeded_client.post(
            "/repos/connect",
            json={"github_repo_id": 7770003, "org_id": str(STUB_ORG_ID)},
        )
        assert res.status_code == 201
        data = res.json()
        assert "initial_run_id" in data
        assert data["initial_run_id"] == str(_FIXED_RUN_ID)
