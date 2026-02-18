"""Unit tests for proposal Pydantic schemas."""

import uuid
from datetime import datetime

from app.proposals.schemas import ArtifactResponse, ProposalCreateRequest, ProposalResponse


class TestProposalResponse:
    def test_full_proposal(self):
        repo_id = uuid.uuid4()
        resp = ProposalResponse(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            repo_id=repo_id,
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
        assert resp.repo_id == repo_id

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
            repo_id=uuid.uuid4(),
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

    def test_artifact_proposal_id_is_nullable(self):
        """Baseline artifacts have no proposal_id."""
        artifact = ArtifactResponse(
            id=uuid.uuid4(),
            proposal_id=None,
            storage_path="artifacts/repos/x/runs/y/baseline.json",
            type="baseline",
            created_at=datetime.now(),
        )
        assert artifact.proposal_id is None


class TestProposalResponseTraces:
    """Verify discovery_trace and patch_trace round-trip through the schema."""

    def _base(self, **overrides):
        defaults = dict(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            repo_id=uuid.uuid4(),
            diff="--- a/x\n+++ b/x",
            summary="Optimize hot path",
            metrics_before=None,
            metrics_after=None,
            risk_score=0.1,
            created_at=datetime.now(),
            pr_url=None,
            artifacts=[],
            discovery_trace=None,
            patch_trace=None,
        )
        defaults.update(overrides)
        return ProposalResponse(**defaults)

    def test_traces_default_to_none(self):
        resp = self._base()
        assert resp.discovery_trace is None
        assert resp.patch_trace is None

    def test_discovery_trace_round_trips(self):
        trace = {
            "model": "claude-sonnet-4-5",
            "provider": "anthropic",
            "reasoning": "Found N+1 query",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "tokens_used": 150,
            "timestamp": "2026-02-18T00:00:00Z",
        }
        resp = self._base(discovery_trace=trace)
        assert resp.discovery_trace == trace

    def test_patch_trace_round_trips(self):
        trace = {"model": "gpt-4o", "provider": "openai", "reasoning": "Generated diff"}
        resp = self._base(patch_trace=trace)
        assert resp.patch_trace == trace

    def test_both_traces_present(self):
        disc = {"reasoning": "discovery"}
        patch = {"reasoning": "patch"}
        resp = self._base(discovery_trace=disc, patch_trace=patch)
        assert resp.discovery_trace == disc
        assert resp.patch_trace == patch


class TestProposalCreateRequestTraces:
    """Verify ProposalCreateRequest accepts and exposes trace fields."""

    def test_traces_optional_and_default_none(self):
        req = ProposalCreateRequest(run_id=uuid.uuid4(), diff="--- a/x\n+++ b/x")
        assert req.discovery_trace is None
        assert req.patch_trace is None

    def test_traces_accepted_when_provided(self):
        disc = {"reasoning": "discovery reasoning"}
        patch = {"reasoning": "patch reasoning"}
        req = ProposalCreateRequest(
            run_id=uuid.uuid4(),
            diff="--- a/x\n+++ b/x",
            discovery_trace=disc,
            patch_trace=patch,
        )
        assert req.discovery_trace == disc
        assert req.patch_trace == patch
