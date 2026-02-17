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
