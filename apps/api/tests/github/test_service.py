"""Tests for GitHub service layer — PR body generation and contract tests."""

import uuid
from datetime import datetime

import pytest

from app.db.models import Proposal
from app.github.service import BRANCH_PREFIX, _build_pr_body


class TestBuildPrBody:
    """Contract tests: verify the PR body contains required evidence."""

    def _make_proposal(self, **overrides) -> Proposal:
        defaults = {
            "id": uuid.uuid4(),
            "run_id": uuid.uuid4(),
            "diff": "--- a/foo.ts\n+++ b/foo.ts",
            "summary": "Replace Array.includes with Set.has",
            "metrics_before": {"avg_latency_ms": 120, "p95_ms": 250},
            "metrics_after": {"avg_latency_ms": 110, "p95_ms": 230},
            "risk_score": 0.15,
        }
        defaults.update(overrides)
        proposal = Proposal(**defaults)
        return proposal

    def test_body_includes_summary(self):
        proposal = self._make_proposal()
        body = _build_pr_body(proposal)
        assert "Replace Array.includes with Set.has" in body

    def test_body_includes_metrics_table(self):
        proposal = self._make_proposal()
        body = _build_pr_body(proposal)
        assert "| avg_latency_ms | 120 | 110 |" in body
        assert "| p95_ms | 250 | 230 |" in body

    def test_body_includes_risk_score(self):
        proposal = self._make_proposal()
        body = _build_pr_body(proposal)
        assert "0.15" in body

    def test_body_includes_selfopt_attribution(self):
        proposal = self._make_proposal()
        body = _build_pr_body(proposal)
        assert "SelfOpt" in body

    def test_body_handles_no_metrics(self):
        proposal = self._make_proposal(
            metrics_before=None,
            metrics_after=None,
        )
        body = _build_pr_body(proposal)
        # Should not crash, and should not contain a metrics table
        assert "Before" not in body
        assert proposal.summary in body

    def test_body_handles_no_summary(self):
        proposal = self._make_proposal(summary=None)
        body = _build_pr_body(proposal)
        assert "SelfOpt" in body


class TestBranchNaming:
    def test_branch_prefix_is_selfopt(self):
        assert BRANCH_PREFIX == "selfopt/proposal-"

    def test_branch_name_format(self):
        proposal_id = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        short_id = str(proposal_id)[:8]
        branch_name = f"{BRANCH_PREFIX}{short_id}"
        assert branch_name == "selfopt/proposal-12345678"
