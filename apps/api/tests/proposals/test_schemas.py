"""Unit tests for proposal Pydantic schemas."""

import uuid
from datetime import datetime

from app.proposals.schemas import ArtifactResponse, ProposalResponse


class TestProposalResponse:
    def test_full_proposal(self):
        resp = ProposalResponse(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            diff="--- a/foo.ts\n+++ b/foo.ts",
            summary="Replace Array.includes with Set.has",
            metrics_before={"latency_ms": 120},
            metrics_after={"latency_ms": 110},
            risk_score=0.2,
            created_at=datetime.now(),
            pr_url=None,
            artifacts=[],
        )
        assert resp.pr_url is None
        assert resp.risk_score == 0.2

    def test_proposal_with_artifacts(self):
        artifact = ArtifactResponse(
            id=uuid.uuid4(),
            proposal_id=uuid.uuid4(),
            storage_path="artifacts/repos/x/runs/y/logs.txt",
            type="log",
            created_at=datetime.now(),
        )
        resp = ProposalResponse(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            diff="diff",
            summary="Test",
            metrics_before=None,
            metrics_after=None,
            risk_score=0,
            created_at=datetime.now(),
            pr_url=None,
            artifacts=[artifact],
        )
        assert len(resp.artifacts) == 1
        assert resp.artifacts[0].type == "log"
