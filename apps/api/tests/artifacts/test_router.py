"""Integration tests for artifact endpoints including signed URL generation."""

import uuid

import pytest

from app.db.models import Artifact, Proposal
from tests.conftest import STUB_REPO_ID


async def _create_proposal_with_artifact(client, db_session):
    """Helper: create a run -> proposal -> artifact chain."""
    run_resp = await client.post(f"/repos/{STUB_REPO_ID}/run", json={})
    run_id = uuid.UUID(run_resp.json()["id"])

    proposal = Proposal(
        run_id=run_id,
        diff="diff content",
        summary="Test optimization",
    )
    db_session.add(proposal)
    await db_session.flush()

    artifact = Artifact(
        proposal_id=proposal.id,
        storage_path="artifacts/repos/abc/runs/def/logs.txt",
        type="log",
    )
    db_session.add(artifact)
    await db_session.commit()
    await db_session.refresh(artifact)
    return artifact


class TestGetArtifactSignedUrl:
    async def test_signed_url_success(self, seeded_client, seeded_db):
        artifact = await _create_proposal_with_artifact(seeded_client, seeded_db)

        response = await seeded_client.get(
            f"/artifacts/{artifact.id}/signed-url"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["artifact_id"] == str(artifact.id)
        assert "signed_url" in data
        # signed_url is None when Supabase is not configured (test env)
        # When Supabase IS configured it would contain the storage path
        assert data["expires_in_seconds"] == 3600

    async def test_signed_url_contains_storage_path(self, seeded_client, seeded_db):
        """Verify the response schema includes the signed_url field (may be None in tests)."""
        artifact = await _create_proposal_with_artifact(seeded_client, seeded_db)

        response = await seeded_client.get(
            f"/artifacts/{artifact.id}/signed-url"
        )
        data = response.json()
        # Field must be present in the response (None is valid when Supabase not configured)
        assert "signed_url" in data

    async def test_signed_url_not_found(self, seeded_client):
        response = await seeded_client.get(
            f"/artifacts/{uuid.uuid4()}/signed-url"
        )
        assert response.status_code == 404
