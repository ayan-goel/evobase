"""Integration tests for proposal endpoints."""

import uuid

import pytest
from sqlalchemy import select

from app.db.models import Artifact, Proposal, Run
from tests.conftest import STUB_REPO_ID


async def _create_run_and_proposal(client, db_session):
    """Helper: enqueue a run, then create a proposal directly in DB."""
    # Create run via API
    run_resp = await client.post(f"/repos/{STUB_REPO_ID}/run", json={})
    run_id = run_resp.json()["id"]

    # Create proposal directly in DB (proposals are created by the runner, not API)
    proposal = Proposal(
        run_id=uuid.UUID(run_id),
        diff="--- a/utils.ts\n+++ b/utils.ts\n-old\n+new",
        summary="Replace Array.includes with Set.has for O(1) lookup",
        metrics_before={"avg_latency_ms": 120},
        metrics_after={"avg_latency_ms": 110},
        risk_score=0.15,
    )
    db_session.add(proposal)
    await db_session.commit()
    await db_session.refresh(proposal)
    return run_id, proposal


class TestGetProposal:
    async def test_get_proposal_success(self, seeded_client, seeded_db):
        run_id, proposal = await _create_run_and_proposal(seeded_client, seeded_db)

        response = await seeded_client.get(f"/proposals/{proposal.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "Replace Array.includes with Set.has for O(1) lookup"
        assert data["metrics_before"]["avg_latency_ms"] == 120
        assert data["pr_url"] is None

    async def test_get_proposal_includes_repo_id(self, seeded_client, seeded_db):
        """repo_id must be present so the frontend can route to /repos/{repo_id}/..."""
        run_id, proposal = await _create_run_and_proposal(seeded_client, seeded_db)

        response = await seeded_client.get(f"/proposals/{proposal.id}")
        assert response.status_code == 200
        data = response.json()
        assert "repo_id" in data
        # repo_id must be a valid UUID and match the repo that owns the run
        assert uuid.UUID(data["repo_id"])  # does not raise
        assert str(STUB_REPO_ID) == data["repo_id"]

    async def test_get_proposal_not_found(self, seeded_client):
        response = await seeded_client.get(f"/proposals/{uuid.uuid4()}")
        assert response.status_code == 404

    async def test_get_proposal_includes_artifacts(self, seeded_client, seeded_db):
        run_id, proposal = await _create_run_and_proposal(seeded_client, seeded_db)

        # Add artifacts to the proposal
        for atype in ["log", "trace", "diff"]:
            seeded_db.add(Artifact(
                proposal_id=proposal.id,
                storage_path=f"artifacts/repos/x/runs/y/{atype}.json",
                type=atype,
            ))
        await seeded_db.commit()

        response = await seeded_client.get(f"/proposals/{proposal.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["artifacts"]) == 3


class TestListProposalsByRun:
    async def test_list_proposals_empty(self, seeded_client, seeded_db):
        run_resp = await seeded_client.post(f"/repos/{STUB_REPO_ID}/run", json={})
        run_id = run_resp.json()["id"]

        response = await seeded_client.get(f"/proposals/by-run/{run_id}")
        assert response.status_code == 200
        assert response.json()["count"] == 0

    async def test_list_proposals_after_creation(self, seeded_client, seeded_db):
        run_id, _ = await _create_run_and_proposal(seeded_client, seeded_db)

        response = await seeded_client.get(f"/proposals/by-run/{run_id}")
        assert response.status_code == 200
        assert response.json()["count"] == 1

    async def test_list_proposals_includes_repo_id(self, seeded_client, seeded_db):
        """Every proposal in the list must carry repo_id."""
        run_id, _ = await _create_run_and_proposal(seeded_client, seeded_db)

        response = await seeded_client.get(f"/proposals/by-run/{run_id}")
        assert response.status_code == 200
        proposals = response.json()["proposals"]
        assert len(proposals) == 1
        assert "repo_id" in proposals[0]
        assert uuid.UUID(proposals[0]["repo_id"])

    async def test_list_proposals_nonexistent_run(self, seeded_client):
        response = await seeded_client.get(f"/proposals/by-run/{uuid.uuid4()}")
        assert response.status_code == 404
