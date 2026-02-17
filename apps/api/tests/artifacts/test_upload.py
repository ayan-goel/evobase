"""Tests for the POST /artifacts/upload endpoint and signed URL generation."""

import uuid

import pytest

from app.db.models import Proposal
from tests.conftest import STUB_REPO_ID


async def _create_run_and_proposal(client, db_session) -> tuple[uuid.UUID, uuid.UUID]:
    """Helper: create a run, then create a proposal via the API."""
    run_resp = await client.post(f"/repos/{STUB_REPO_ID}/run", json={})
    assert run_resp.status_code == 201
    run_id = uuid.UUID(run_resp.json()["id"])

    prop_resp = await client.post("/proposals/create", json={
        "run_id": str(run_id),
        "diff": "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-x\n+y\n",
        "summary": "test proposal",
        "confidence": "high",
    })
    assert prop_resp.status_code == 201
    proposal_id = uuid.UUID(prop_resp.json()["id"])

    return run_id, proposal_id


class TestArtifactUpload:
    async def test_uploads_artifact_successfully(self, seeded_client, seeded_db):
        _, proposal_id = await _create_run_and_proposal(seeded_client, seeded_db)

        resp = await seeded_client.post("/artifacts/upload", json={
            "proposal_id": str(proposal_id),
            "storage_path": "repos/r/runs/r/proposal.json",
            "type": "proposal",
            "content": '{"schema_version": "1.0"}',
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["proposal_id"] == str(proposal_id)
        assert data["storage_path"] == "repos/r/runs/r/proposal.json"
        assert data["type"] == "proposal"
        assert data["uploaded"] is True
        assert "id" in data

    async def test_upload_without_content(self, seeded_client, seeded_db):
        """Content field is optional — storage_path is the durable reference."""
        _, proposal_id = await _create_run_and_proposal(seeded_client, seeded_db)

        resp = await seeded_client.post("/artifacts/upload", json={
            "proposal_id": str(proposal_id),
            "storage_path": "repos/r/runs/r/diff.patch",
            "type": "diff",
        })
        assert resp.status_code == 201

    async def test_upload_returns_404_for_missing_proposal(self, seeded_client):
        resp = await seeded_client.post("/artifacts/upload", json={
            "proposal_id": str(uuid.uuid4()),
            "storage_path": "repos/r/runs/r/trace.json",
            "type": "trace",
        })
        assert resp.status_code == 404

    async def test_upload_empty_storage_path_fails(self, seeded_client, seeded_db):
        _, proposal_id = await _create_run_and_proposal(seeded_client, seeded_db)
        resp = await seeded_client.post("/artifacts/upload", json={
            "proposal_id": str(proposal_id),
            "storage_path": "",  # min_length=1
            "type": "proposal",
        })
        assert resp.status_code == 422

    async def test_uploaded_artifact_appears_in_proposal(self, seeded_client, seeded_db):
        run_id, proposal_id = await _create_run_and_proposal(seeded_client, seeded_db)

        # Upload an artifact
        await seeded_client.post("/artifacts/upload", json={
            "proposal_id": str(proposal_id),
            "storage_path": "repos/r/runs/r/trace.json",
            "type": "trace",
        })

        # Retrieve proposal — artifacts should be included
        prop_resp = await seeded_client.get(f"/proposals/{proposal_id}")
        assert prop_resp.status_code == 200
        artifacts = prop_resp.json()["artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0]["type"] == "trace"
        assert artifacts[0]["storage_path"] == "repos/r/runs/r/trace.json"

    async def test_multiple_artifacts_per_proposal(self, seeded_client, seeded_db):
        _, proposal_id = await _create_run_and_proposal(seeded_client, seeded_db)

        for artifact_type, path in [
            ("proposal", "p.json"),
            ("diff", "d.patch"),
            ("trace", "t.json"),
        ]:
            resp = await seeded_client.post("/artifacts/upload", json={
                "proposal_id": str(proposal_id),
                "storage_path": f"repos/r/runs/r/{path}",
                "type": artifact_type,
            })
            assert resp.status_code == 201

        prop_resp = await seeded_client.get(f"/proposals/{proposal_id}")
        assert len(prop_resp.json()["artifacts"]) == 3


class TestSignedUrl:
    async def test_signed_url_after_upload(self, seeded_client, seeded_db):
        _, proposal_id = await _create_run_and_proposal(seeded_client, seeded_db)

        upload_resp = await seeded_client.post("/artifacts/upload", json={
            "proposal_id": str(proposal_id),
            "storage_path": "repos/r/runs/r/proposal.json",
            "type": "proposal",
        })
        artifact_id = upload_resp.json()["id"]

        signed_resp = await seeded_client.get(f"/artifacts/{artifact_id}/signed-url")
        assert signed_resp.status_code == 200
        data = signed_resp.json()
        assert data["artifact_id"] == artifact_id
        # signed_url is None when Supabase is not configured in test env
        assert "signed_url" in data
        assert data["expires_in_seconds"] == 3600

    async def test_signed_url_not_found(self, seeded_client):
        resp = await seeded_client.get(f"/artifacts/{uuid.uuid4()}/signed-url")
        assert resp.status_code == 404


class TestProposalSchemaValidation:
    """Schema-level validation tests for ProposalCreateRequest."""

    async def test_confidence_values_accepted(self, seeded_client):
        run_resp = await seeded_client.post(f"/repos/{STUB_REPO_ID}/run", json={})
        run_id = run_resp.json()["id"]

        for confidence in ["high", "medium", "low"]:
            resp = await seeded_client.post("/proposals/create", json={
                "run_id": run_id,
                "diff": "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-x\n+y\n",
                "confidence": confidence,
            })
            assert resp.status_code == 201, f"confidence={confidence} should be accepted"
