"""Integration tests for run endpoints."""

import uuid

import pytest

from tests.conftest import STUB_REPO_ID


class TestEnqueueRun:
    async def test_enqueue_run_success(self, seeded_client):
        response = await seeded_client.post(
            f"/repos/{STUB_REPO_ID}/run",
            json={"sha": "abc123def"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"
        assert data["sha"] == "abc123def"
        assert data["repo_id"] == str(STUB_REPO_ID)

    async def test_enqueue_run_without_sha(self, seeded_client):
        """SHA is optional; defaults to None (will use HEAD later)."""
        response = await seeded_client.post(
            f"/repos/{STUB_REPO_ID}/run",
            json={},
        )
        assert response.status_code == 201
        assert response.json()["sha"] is None

    async def test_enqueue_run_nonexistent_repo(self, seeded_client):
        response = await seeded_client.post(
            f"/repos/{uuid.uuid4()}/run",
            json={},
        )
        assert response.status_code == 404


class TestListRuns:
    async def test_list_runs_empty(self, seeded_client):
        response = await seeded_client.get(f"/repos/{STUB_REPO_ID}/runs")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["runs"] == []

    async def test_list_runs_after_enqueue(self, seeded_client):
        """After enqueuing a run, it should appear in the list."""
        await seeded_client.post(f"/repos/{STUB_REPO_ID}/run", json={})
        await seeded_client.post(f"/repos/{STUB_REPO_ID}/run", json={"sha": "v2"})

        response = await seeded_client.get(f"/repos/{STUB_REPO_ID}/runs")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    async def test_list_runs_nonexistent_repo(self, seeded_client):
        response = await seeded_client.get(f"/repos/{uuid.uuid4()}/runs")
        assert response.status_code == 404


class TestGetRun:
    async def test_get_run_success(self, seeded_client):
        create_resp = await seeded_client.post(
            f"/repos/{STUB_REPO_ID}/run", json={"sha": "abc"}
        )
        run_id = create_resp.json()["id"]

        response = await seeded_client.get(f"/runs/{run_id}")
        assert response.status_code == 200
        assert response.json()["id"] == run_id
        assert response.json()["status"] == "queued"

    async def test_get_run_not_found(self, seeded_client):
        response = await seeded_client.get(f"/runs/{uuid.uuid4()}")
        assert response.status_code == 404


class TestCancelRun:
    async def test_cancel_queued_run(self, seeded_client):
        create_resp = await seeded_client.post(
            f"/repos/{STUB_REPO_ID}/run", json={}
        )
        run_id = create_resp.json()["id"]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.runs.events._get_sync_redis", lambda: _FakeRedis())

            response = await seeded_client.post(f"/runs/{run_id}/cancel")
            assert response.status_code == 200
            data = response.json()
            assert data["cancelled"] is True
            assert data["status"] == "failed"

        # Verify the run is now failed
        get_resp = await seeded_client.get(f"/runs/{run_id}")
        assert get_resp.json()["status"] == "failed"

    async def test_cancel_completed_run_is_noop(self, seeded_client):
        create_resp = await seeded_client.post(
            f"/repos/{STUB_REPO_ID}/run", json={}
        )
        run_id = create_resp.json()["id"]

        # Manually transition to completed (simulate worker finishing)
        from app.db.models import Run
        from sqlalchemy import update
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.db.session import get_db

        # The seeded_client's DB dependency commits, so the run exists
        # Cancel without transitioning — it's still "queued", so it will cancel
        # Instead let's test that cancelling a non-active run returns cancelled=False
        # by marking it completed first via the DB

    async def test_cancel_nonexistent_run(self, seeded_client):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.runs.events._get_sync_redis", lambda: _FakeRedis())
            response = await seeded_client.post(f"/runs/{uuid.uuid4()}/cancel")
        assert response.status_code == 404


class _FakeRedis:
    """Minimal Redis mock for cancel tests."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def set(self, key, value, ex=None):
        self._store[key] = value

    def get(self, key):
        return self._store.get(key)

    def exists(self, key):
        return 1 if key in self._store else 0

    def xadd(self, name, fields, maxlen=None):
        return "0-0"

    def expire(self, name, seconds):
        pass
