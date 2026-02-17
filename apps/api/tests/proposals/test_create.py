"""Tests for the POST /proposals/create endpoint."""

import uuid

import pytest

from app.db.models import Run
from tests.conftest import STUB_REPO_ID


async def _create_run(seeded_client) -> uuid.UUID:
    resp = await seeded_client.post(f"/repos/{STUB_REPO_ID}/run", json={})
    assert resp.status_code == 201
    return uuid.UUID(resp.json()["id"])


class TestCreateProposal:
    async def test_creates_proposal_successfully(self, seeded_client):
        run_id = await _create_run(seeded_client)

        resp = await seeded_client.post("/proposals/create", json={
            "run_id": str(run_id),
            "diff": "--- a/f.ts\n+++ b/f.ts\n@@ -1 +1 @@\n-old\n+new\n",
            "summary": "Replaced indexOf with includes",
            "risk_score": 0.2,
            "confidence": "high",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["run_id"] == str(run_id)
        assert data["summary"] == "Replaced indexOf with includes"
        assert data["confidence"] == "high"
        assert data["risk_score"] == pytest.approx(0.2, abs=0.001)

    def test_proposal_response_has_id(self, seeded_client):
        async def run():
            run_id = await _create_run(seeded_client)
            resp = await seeded_client.post("/proposals/create", json={
                "run_id": str(run_id),
                "diff": "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-x\n+y\n",
            })
            assert "id" in resp.json()
        import asyncio; asyncio.get_event_loop().run_until_complete(run())

    async def test_proposal_with_metrics(self, seeded_client):
        run_id = await _create_run(seeded_client)
        metrics = {"is_success": True, "step_count": 2, "total_duration_seconds": 5.1}

        resp = await seeded_client.post("/proposals/create", json={
            "run_id": str(run_id),
            "diff": "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-x\n+y\n",
            "metrics_before": metrics,
            "metrics_after": {**metrics, "total_duration_seconds": 4.9},
            "confidence": "medium",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["metrics_before"]["step_count"] == 2
        assert data["confidence"] == "medium"

    async def test_returns_404_for_nonexistent_run(self, seeded_client):
        resp = await seeded_client.post("/proposals/create", json={
            "run_id": str(uuid.uuid4()),
            "diff": "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-x\n+y\n",
        })
        assert resp.status_code == 404

    async def test_returns_422_for_empty_diff(self, seeded_client):
        run_id = await _create_run(seeded_client)
        resp = await seeded_client.post("/proposals/create", json={
            "run_id": str(run_id),
            "diff": "",  # min_length=1 validation
        })
        assert resp.status_code == 422

    async def test_optional_fields_default_to_none(self, seeded_client):
        run_id = await _create_run(seeded_client)
        resp = await seeded_client.post("/proposals/create", json={
            "run_id": str(run_id),
            "diff": "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-x\n+y\n",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["summary"] is None
        assert data["confidence"] is None
        # risk_score defaults to 0 from the model's column default
        assert data["risk_score"] in (None, 0, 0.0)

    async def test_proposal_appears_in_list_by_run(self, seeded_client):
        run_id = await _create_run(seeded_client)

        create_resp = await seeded_client.post("/proposals/create", json={
            "run_id": str(run_id),
            "diff": "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-x\n+y\n",
            "summary": "list test",
        })
        assert create_resp.status_code == 201

        # List proposals by run (requires auth stub)
        list_resp = await seeded_client.get(f"/proposals/by-run/{run_id}")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["count"] == 1
        assert data["proposals"][0]["summary"] == "list test"

    async def test_risk_score_must_be_in_range(self, seeded_client):
        run_id = await _create_run(seeded_client)
        resp = await seeded_client.post("/proposals/create", json={
            "run_id": str(run_id),
            "diff": "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-x\n+y\n",
            "risk_score": 1.5,  # > 1.0 — should fail
        })
        assert resp.status_code == 422
