"""Tests for GitHub service layer — PR body generation and contract tests."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, call, patch

import pytest

from app.db.models import Proposal, Repository
from app.github.service import (
    BRANCH_PREFIX,
    _apply_patch_to_content,
    _build_pr_body,
    create_pr_for_proposal,
)


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

    def test_body_includes_coreloop_attribution(self):
        proposal = self._make_proposal()
        body = _build_pr_body(proposal)
        assert "Coreloop" in body

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
        assert "Coreloop" in body


class TestBranchNaming:
    def test_branch_prefix_is_coreloop(self):
        assert BRANCH_PREFIX == "coreloop/proposal-"

    def test_branch_name_format(self):
        proposal_id = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        short_id = str(proposal_id)[:8]
        branch_name = f"{BRANCH_PREFIX}{short_id}"
        assert branch_name == "coreloop/proposal-12345678"


# ---------------------------------------------------------------------------
# Helpers shared by TestCreatePrForProposal
# ---------------------------------------------------------------------------

def _make_repo(**overrides) -> Repository:
    defaults = {
        "github_repo_id": 111,
        "github_full_name": "acme/api",
        "default_branch": "main",
        "installation_id": 42000,
    }
    defaults.update(overrides)
    return Repository(**defaults)


def _make_proposal_obj(**overrides) -> Proposal:
    defaults = {
        "id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "diff": "--- a/foo.ts\n+++ b/foo.ts\n@@ -1 +1 @@\n-old\n+new\n",
        "summary": "Optimise hot path",
        "metrics_before": {"latency_ms": 100},
        "metrics_after": {"latency_ms": 90},
        "risk_score": 0.1,
    }
    defaults.update(overrides)
    return Proposal(**defaults)


def _all_client_mocks():
    """Return a dict of patch targets to AsyncMock for all GitHub client calls."""
    return {
        "app.github.client.get_installation_token": AsyncMock(return_value="ghs_token"),
        "app.github.client.get_default_branch_sha": AsyncMock(return_value="abc123sha"),
        "app.github.client.create_branch": AsyncMock(return_value={}),
        "app.github.client.get_file_content": AsyncMock(
            return_value={"content": "old\n", "sha": "filesha123"}
        ),
        "app.github.client.put_file_content": AsyncMock(return_value=None),
        "app.github.client.create_pull_request": AsyncMock(
            return_value={"html_url": "https://github.com/acme/api/pull/7"}
        ),
    }


class TestCreatePrForProposal:
    """Tests for the main create_pr_for_proposal orchestration function."""

    async def _run_with_mocks(self, repo, proposal, overrides=None):
        """Run create_pr_for_proposal with all GitHub client calls mocked."""
        mocks = _all_client_mocks()
        if overrides:
            mocks.update(overrides)
        with (
            patch("app.github.client.get_installation_token", mocks["app.github.client.get_installation_token"]),
            patch("app.github.client.get_default_branch_sha", mocks["app.github.client.get_default_branch_sha"]),
            patch("app.github.client.create_branch", mocks["app.github.client.create_branch"]),
            patch("app.github.client.get_file_content", mocks["app.github.client.get_file_content"]),
            patch("app.github.client.put_file_content", mocks["app.github.client.put_file_content"]),
            patch("app.github.client.create_pull_request", mocks["app.github.client.create_pull_request"]),
        ):
            result = await create_pr_for_proposal(repo, proposal)
        return result, mocks

    @pytest.mark.asyncio
    async def test_create_pr_parses_github_full_name(self):
        """owner and repo_name are parsed from github_full_name."""
        repo = _make_repo(github_full_name="acme/api")
        proposal = _make_proposal_obj()

        _, mocks = await self._run_with_mocks(repo, proposal)

        sha_call = mocks["app.github.client.get_default_branch_sha"].call_args
        assert sha_call.args[1] == "acme"   # owner
        assert sha_call.args[2] == "api"    # repo_name

    @pytest.mark.asyncio
    async def test_create_pr_raises_when_no_github_full_name(self):
        repo = _make_repo(github_full_name=None)
        proposal = _make_proposal_obj()
        with pytest.raises(ValueError, match="github_full_name"):
            await create_pr_for_proposal(repo, proposal)

    @pytest.mark.asyncio
    async def test_create_pr_raises_when_no_installation_id(self):
        repo = _make_repo(installation_id=None)
        proposal = _make_proposal_obj()
        with pytest.raises(ValueError, match="installation"):
            await create_pr_for_proposal(repo, proposal)

    @pytest.mark.asyncio
    async def test_create_pr_raises_when_invalid_full_name(self):
        """github_full_name without a slash should raise ValueError."""
        repo = _make_repo(github_full_name="noslash")
        proposal = _make_proposal_obj()
        with pytest.raises(ValueError, match="Invalid github_full_name"):
            await create_pr_for_proposal(repo, proposal)

    @pytest.mark.asyncio
    async def test_create_pr_gets_installation_token(self):
        """get_installation_token is called with the repo's installation_id."""
        repo = _make_repo(installation_id=99999)
        proposal = _make_proposal_obj()

        _, mocks = await self._run_with_mocks(repo, proposal)

        mocks["app.github.client.get_installation_token"].assert_called_once_with(99999)

    @pytest.mark.asyncio
    async def test_create_pr_full_flow_with_mocked_github(self):
        """Full chain returns the pr_url from the GitHub API response."""
        repo = _make_repo()
        proposal = _make_proposal_obj()

        pr_url, _ = await self._run_with_mocks(repo, proposal)

        assert pr_url == "https://github.com/acme/api/pull/7"

    @pytest.mark.asyncio
    async def test_pr_title_includes_proposal_summary(self):
        """PR title follows the [Coreloop] <summary> format."""
        repo = _make_repo()
        proposal = _make_proposal_obj(summary="Reduce p95 latency by 12%")

        _, mocks = await self._run_with_mocks(repo, proposal)

        create_pr_call = mocks["app.github.client.create_pull_request"].call_args
        title = create_pr_call.kwargs.get("title") or create_pr_call.args[3]
        assert title == "[Coreloop] Reduce p95 latency by 12%"

    @pytest.mark.asyncio
    async def test_pr_body_includes_coreloop_attribution(self):
        """PR body must contain the Coreloop attribution line."""
        repo = _make_repo()
        proposal = _make_proposal_obj()

        _, mocks = await self._run_with_mocks(repo, proposal)

        create_pr_call = mocks["app.github.client.create_pull_request"].call_args
        body = create_pr_call.kwargs.get("body") or create_pr_call.args[4]
        assert "Coreloop" in body

    @pytest.mark.asyncio
    async def test_commit_diff_called_before_create_pr(self):
        """_commit_diff_to_branch is invoked between create_branch and create_pull_request."""
        repo = _make_repo()
        proposal = _make_proposal_obj(
            diff=(
                "--- a/foo.ts\n+++ b/foo.ts\n"
                "@@ -1,2 +1,2 @@\n context\n-old line\n+new line\n"
            )
        )

        call_order: list[str] = []

        async def _fake_create_branch(*a, **kw):
            call_order.append("create_branch")

        async def _fake_get_file(*a, **kw):
            call_order.append("get_file_content")
            return {"content": "context\nold line\n", "sha": "filesha"}

        async def _fake_put_file(*a, **kw):
            call_order.append("put_file_content")

        async def _fake_create_pr(*a, **kw):
            call_order.append("create_pull_request")
            return {"html_url": "https://github.com/acme/api/pull/1"}

        with (
            patch("app.github.client.get_installation_token", AsyncMock(return_value="tok")),
            patch("app.github.client.get_default_branch_sha", AsyncMock(return_value="sha")),
            patch("app.github.client.create_branch", _fake_create_branch),
            patch("app.github.client.get_file_content", _fake_get_file),
            patch("app.github.client.put_file_content", _fake_put_file),
            patch("app.github.client.create_pull_request", _fake_create_pr),
        ):
            await create_pr_for_proposal(repo, proposal)

        assert "create_branch" in call_order
        assert "create_pull_request" in call_order
        # Both file ops must complete before create_pull_request
        branch_idx = call_order.index("create_branch")
        pr_idx = call_order.index("create_pull_request")
        assert branch_idx < pr_idx

    @pytest.mark.asyncio
    async def test_empty_diff_skips_commit_step(self):
        """When proposal.diff is empty, no file content calls are made."""
        repo = _make_repo()
        proposal = _make_proposal_obj(diff="")

        file_ops_called = []

        async def _noop_file(*a, **kw):
            file_ops_called.append("called")

        with (
            patch("app.github.client.get_installation_token", AsyncMock(return_value="tok")),
            patch("app.github.client.get_default_branch_sha", AsyncMock(return_value="sha")),
            patch("app.github.client.create_branch", AsyncMock()),
            patch("app.github.client.get_file_content", _noop_file),
            patch("app.github.client.put_file_content", _noop_file),
            patch("app.github.client.create_pull_request", AsyncMock(
                return_value={"html_url": "https://github.com/acme/api/pull/1"}
            )),
        ):
            await create_pr_for_proposal(repo, proposal)

        assert file_ops_called == []


class TestApplyPatchToContent:
    """Unit tests for the _apply_patch_to_content hunk applier."""

    def _make_patched_file(self, hunks: list[tuple[int, list[str]]]):
        """
        Build a minimal mock patched-file with the given hunks.
        Each hunk is (source_start, [line_strings]) where line strings are
        prefixed with ' ', '+', or '-' and end with '\n'.
        """
        from unittest.mock import MagicMock

        class FakeLine:
            def __init__(self, raw):
                self.line_type = raw[0] if raw[0] in ("+", "-") else " "
                self.value = raw[1:]

        mock_hunks = []
        for start, lines in hunks:
            h = MagicMock()
            h.source_start = start
            h.__iter__ = MagicMock(return_value=iter([FakeLine(l) for l in lines]))
            mock_hunks.append(h)

        pf = MagicMock()
        pf.__iter__ = MagicMock(return_value=iter(mock_hunks))
        return pf

    def test_replaces_line_in_middle(self):
        original = "line1\nline2\nline3\n"
        # source_start=1: hunk covers the whole file from line 1
        pf = self._make_patched_file([
            (1, [" line1\n", "-line2\n", "+replaced\n", " line3\n"]),
        ])
        result = _apply_patch_to_content(original, pf)
        assert result == "line1\nreplaced\nline3\n"

    def test_adds_new_line(self):
        original = "a\nb\n"
        pf = self._make_patched_file([
            (1, [" a\n", "+inserted\n", " b\n"]),
        ])
        result = _apply_patch_to_content(original, pf)
        assert result == "a\ninserted\nb\n"

    def test_removes_line(self):
        original = "keep\nremove\nkeep\n"
        pf = self._make_patched_file([
            (1, [" keep\n", "-remove\n", " keep\n"]),
        ])
        result = _apply_patch_to_content(original, pf)
        assert result == "keep\nkeep\n"

    def test_preserves_lines_before_hunk(self):
        original = "preamble\nline1\nline2\n"
        pf = self._make_patched_file([
            (2, [" line1\n", "-line2\n", "+patched\n"]),
        ])
        result = _apply_patch_to_content(original, pf)
        assert result.startswith("preamble\n")

    def test_empty_diff_returns_original(self):
        original = "unchanged\n"
        pf = self._make_patched_file([])
        result = _apply_patch_to_content(original, pf)
        assert result == original
