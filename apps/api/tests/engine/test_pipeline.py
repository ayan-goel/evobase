"""Phase 16: Pipeline wiring tests.

Tests for the full execute_full_pipeline() flow. All external side-effects
(repo clone, LLM calls, Supabase) are mocked so tests run offline without
any real credentials.

The tests verify:
  1. State transitions (queued → running → completed/failed) actually write to DB
  2. Happy path: baseline passes, LLM produces proposals, proposals written to DB
  3. Baseline failure: run is marked failed, failure counter incremented
  4. No LLM key: baseline-only result, no agent cycle
  5. No github_repo_id: early return with structured result
  6. Cleanup: temp directory always removed (even on error)
"""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.db.models import Opportunity, Proposal, Repository, Run, Settings
from app.runs.service import RunService, _write_proposals_to_db, validate_transition
from tests.conftest import STUB_ORG_ID, STUB_REPO_ID, STUB_USER_ID


# ============================================================================
# Helpers to build mock runner objects
# ============================================================================

def _make_detection(
    package_manager="npm",
    framework="next",
    install_cmd="npm ci",
    build_cmd="npm run build",
    test_cmd="npm test",
    typecheck_cmd=None,
):
    m = MagicMock()
    m.package_manager = package_manager
    m.framework = framework
    m.install_cmd = install_cmd
    m.build_cmd = build_cmd
    m.test_cmd = test_cmd
    m.typecheck_cmd = typecheck_cmd
    return m


def _make_baseline(is_success=True):
    m = MagicMock()
    m.is_success = is_success
    m.steps = []
    m.to_dict.return_value = {"is_success": is_success, "steps": []}
    return m


def _make_thinking_trace():
    t = MagicMock()
    t.to_dict.return_value = {
        "model": "claude-sonnet-4-5",
        "provider": "anthropic",
        "reasoning": "test reasoning",
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return t


def _make_agent_opportunity(location="src/app.ts", category="performance"):
    opp = MagicMock()
    opp.location = location
    opp.category = category
    opp.rationale = "This can be optimized"
    opp.risk_score = 0.3
    opp.thinking_trace = _make_thinking_trace()
    return opp


def _make_agent_patch(diff="--- a/src/app.ts\n+++ b/src/app.ts\n@@ -1 +1 @@\n-old\n+new"):
    patch = MagicMock()
    patch.diff = diff
    patch.explanation = "Optimized the hot path"
    patch.touched_files = ["src/app.ts"]
    patch.estimated_lines_changed = 2
    patch.thinking_trace = _make_thinking_trace()
    return patch


def _make_verdict(is_accepted=True, confidence="high"):
    v = MagicMock()
    v.is_accepted = is_accepted
    v.confidence = confidence
    v.reason = "All gates passed"
    v.gates_failed = []
    return v


def _make_candidate(is_accepted=True, confidence="high"):
    c = MagicMock()
    c.is_accepted = is_accepted
    v = _make_verdict(is_accepted, confidence)
    c.final_verdict = v
    c.attempts = [MagicMock()]
    return c


def _make_cycle_result(n_accepted=2, n_rejected=1):
    opp_list = [_make_agent_opportunity(f"src/file{i}.ts") for i in range(n_accepted + n_rejected)]
    patch_list = [_make_agent_patch() for _ in range(n_accepted + n_rejected)]
    candidate_list = (
        [_make_candidate(True, "high") for _ in range(n_accepted)]
        + [_make_candidate(False, "low") for _ in range(n_rejected)]
    )

    agent_run = MagicMock()
    agent_run.model = "claude-sonnet-4-5"
    agent_run.provider = "anthropic"
    agent_run.patches = patch_list
    agent_run.errors = [None] * len(patch_list)

    cycle = MagicMock()
    cycle.agent_run = agent_run
    cycle.candidate_results = candidate_list
    cycle.opportunity_for_candidate = opp_list
    cycle.total_attempted = n_accepted + n_rejected
    cycle.accepted_count = n_accepted
    return cycle


# ============================================================================
# Tests: _write_proposals_to_db (uses real in-memory SQLite via conftest)
# ============================================================================

class TestWriteProposalsToDb:
    """Tests for _write_proposals_to_db using a mocked sync session.

    We use a mock session instead of a real SQLite session here because
    _write_proposals_to_db is a synchronous function that calls get_sync_db()
    internally, and bridging async/sync sessions in pytest-asyncio tests is
    fragile. The DB write logic is straightforward and well-covered by the
    mock assertions.
    """

    def _make_mock_session(self, run_id, repo_id):
        """Return a mock sync session that simulates flush() returning objects with IDs."""
        session = MagicMock()

        def add_side_effect(obj):
            # Simulate flush() giving the object an ID
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        session.add.side_effect = add_side_effect

        def flush_side_effect():
            pass  # IDs are set in add_side_effect

        session.flush.side_effect = flush_side_effect
        return session

    def test_writes_proposals_for_accepted_candidates(self) -> None:
        """Accepted candidates produce Proposal + Opportunity + Attempt rows."""
        run_id = str(uuid.uuid4())
        repo_id = str(uuid.uuid4())
        cycle = _make_cycle_result(n_accepted=2, n_rejected=1)
        baseline = _make_baseline()

        with patch("app.runs.service.get_sync_db") as mock_db:
            session = self._make_mock_session(run_id, repo_id)
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            count = _write_proposals_to_db(
                run_id=run_id,
                repo_id=repo_id,
                cycle_result=cycle,
                baseline=baseline,
                max_proposals=10,
            )

        # 2 accepted + 1 rejected = 3 add() calls for Opportunity
        # 3 add() calls for Attempt
        # 2 add() calls for Proposal
        assert count == 2
        assert session.add.call_count == 3 + 3 + 2  # opps + attempts + proposals
        session.commit.assert_called_once()

    def test_respects_max_proposals_limit(self) -> None:
        """max_proposals caps the number of Proposal rows created."""
        run_id = str(uuid.uuid4())
        repo_id = str(uuid.uuid4())
        cycle = _make_cycle_result(n_accepted=5, n_rejected=0)
        baseline = _make_baseline()

        with patch("app.runs.service.get_sync_db") as mock_db:
            session = self._make_mock_session(run_id, repo_id)
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            count = _write_proposals_to_db(
                run_id=run_id,
                repo_id=repo_id,
                cycle_result=cycle,
                baseline=baseline,
                max_proposals=3,
            )

        assert count == 3

    def test_no_proposals_for_all_rejected(self) -> None:
        """All-rejected cycle produces 0 proposals but still writes opp+attempt rows."""
        run_id = str(uuid.uuid4())
        repo_id = str(uuid.uuid4())
        cycle = _make_cycle_result(n_accepted=0, n_rejected=3)
        baseline = _make_baseline()

        with patch("app.runs.service.get_sync_db") as mock_db:
            session = self._make_mock_session(run_id, repo_id)
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            count = _write_proposals_to_db(
                run_id=run_id,
                repo_id=repo_id,
                cycle_result=cycle,
                baseline=baseline,
                max_proposals=10,
            )

        assert count == 0


# ============================================================================
# Tests: RunService.transition_to_* with mocked sync session
# ============================================================================

class TestRunServiceTransitions:
    def _make_run(self, status="queued", run_id=None):
        run = MagicMock(spec=Run)
        run.id = run_id or uuid.uuid4()
        run.status = status
        run.repo_id = STUB_REPO_ID
        run.sha = "abc123"
        return run

    def test_transition_to_running_updates_status(self) -> None:
        run = self._make_run("queued")

        with patch("app.runs.service.get_sync_db") as mock_db:
            session = MagicMock()
            session.get.return_value = run
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            RunService().transition_to_running(str(run.id))

        assert run.status == "running"
        session.commit.assert_called_once()

    def test_transition_to_completed_updates_status(self) -> None:
        run = self._make_run("running")

        with patch("app.runs.service.get_sync_db") as mock_db:
            session = MagicMock()
            session.get.return_value = run
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            RunService().transition_to_completed(str(run.id), {})

        assert run.status == "completed"
        session.commit.assert_called_once()

    def test_transition_to_failed_updates_status(self) -> None:
        run = self._make_run("running")

        with patch("app.runs.service.get_sync_db") as mock_db:
            session = MagicMock()
            session.get.return_value = run
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            RunService().transition_to_failed(str(run.id), "some error")

        assert run.status == "failed"

    def test_transition_run_not_found_raises(self) -> None:
        with patch("app.runs.service.get_sync_db") as mock_db:
            session = MagicMock()
            session.get.return_value = None
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            with pytest.raises(ValueError, match="not found"):
                RunService().transition_to_running(str(uuid.uuid4()))


# ============================================================================
# Tests: execute_full_pipeline — full flow with mocked runner
# ============================================================================

class TestExecuteFullPipeline:
    def _mock_db_session(self, run_mock, repo_mock, settings_mock=None):
        """Return a mock sync session that returns the given objects."""
        session = MagicMock()

        def mock_get(model, pk):
            if model == Run:
                return run_mock
            if model == Repository:
                return repo_mock
            if model == Settings:
                return settings_mock or _make_settings()
            return None

        session.get.side_effect = mock_get
        return session

    def _make_run_mock(self, run_id=None):
        r = MagicMock(spec=Run)
        r.id = uuid.UUID(run_id) if run_id else uuid.uuid4()
        r.repo_id = STUB_REPO_ID
        r.sha = None
        r.trace_id = str(uuid.uuid4())
        return r

    def _make_repo_mock(self, github_repo_id=12345678, github_full_name="acme/test-repo"):
        r = MagicMock(spec=Repository)
        r.id = STUB_REPO_ID
        r.github_repo_id = github_repo_id
        r.github_full_name = github_full_name
        r.install_cmd = None
        r.build_cmd = None
        r.test_cmd = None
        r.typecheck_cmd = None
        r.package_manager = None
        return r

    def test_returns_no_github_repo_id_result_when_repo_has_none(self) -> None:
        """If both github_repo_id and github_full_name are null, pipeline exits early."""
        run = self._make_run_mock()
        repo = self._make_repo_mock(github_repo_id=None, github_full_name=None)

        with patch("app.runs.service.get_sync_db") as mock_db:
            session = MagicMock()
            session.get.side_effect = lambda m, pk: run if m == Run else (
                repo if m == Repository else _make_settings()
            )
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            result = RunService().execute_full_pipeline(str(run.id))

        assert result["reason"] == "no_github_repo_id"
        assert result["baseline_completed"] is False

    def test_returns_baseline_failed_result_on_install_failure(self) -> None:
        """If the baseline (install/test) fails, agent is skipped."""
        run = self._make_run_mock()
        repo = self._make_repo_mock()

        with patch("app.runs.service.get_sync_db") as mock_db, \
             patch("runner.sandbox.checkout.clone_repo"), \
             patch("runner.detector.orchestrator.detect", return_value=_make_detection()), \
             patch("runner.validator.executor.run_baseline", return_value=_make_baseline(is_success=False)), \
             patch("app.runs.service._increment_failure_counter"):

            session = MagicMock()
            session.get.side_effect = lambda m, pk: run if m == Run else (
                repo if m == Repository else _make_settings()
            )
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            result = RunService().execute_full_pipeline(str(run.id))

        assert result["reason"] == "baseline_failed"
        assert result["baseline_completed"] is False

    def test_returns_no_llm_key_result_when_key_missing(self) -> None:
        """If no LLM API key is configured, agent cycle is skipped."""
        run = self._make_run_mock()
        repo = self._make_repo_mock()

        with patch("app.runs.service.get_sync_db") as mock_db, \
             patch("runner.sandbox.checkout.clone_repo"), \
             patch("runner.detector.orchestrator.detect", return_value=_make_detection()), \
             patch("runner.validator.executor.run_baseline", return_value=_make_baseline()), \
             patch("app.runs.service._upload_baseline_artifacts"), \
             patch("app.runs.service._resolve_api_key", return_value=""):

            session = MagicMock()
            session.get.side_effect = lambda m, pk: run if m == Run else (
                repo if m == Repository else _make_settings()
            )
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            result = RunService().execute_full_pipeline(str(run.id))

        assert result["reason"] == "no_llm_api_key"
        assert result["baseline_completed"] is True

    def test_happy_path_returns_proposals_count(self) -> None:
        """Full pipeline: baseline passes, agent runs, proposals written."""
        run = self._make_run_mock()
        repo = self._make_repo_mock()
        cycle = _make_cycle_result(n_accepted=2, n_rejected=1)

        with patch("app.runs.service.get_sync_db") as mock_db, \
             patch("runner.sandbox.checkout.clone_repo"), \
             patch("runner.detector.orchestrator.detect", return_value=_make_detection()), \
             patch("runner.validator.executor.run_baseline", return_value=_make_baseline()), \
             patch("app.runs.service._upload_baseline_artifacts"), \
             patch("app.runs.service._resolve_api_key", return_value="sk-test-key"), \
             patch("runner.agent.orchestrator.run_agent_cycle", new=AsyncMock(return_value=cycle)), \
             patch("app.runs.service._write_proposals_to_db", return_value=2) as mock_write, \
             patch("app.runs.service._update_settings_after_success"):

            session = MagicMock()
            session.get.side_effect = lambda m, pk: run if m == Run else (
                repo if m == Repository else _make_settings()
            )
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            result = RunService().execute_full_pipeline(str(run.id))

        assert result["baseline_completed"] is True
        assert result["agent_completed"] is True
        assert result["proposals_created"] == 2
        assert result["candidates_attempted"] == 3
        mock_write.assert_called_once()

    def test_temp_directory_cleaned_up_after_clone(self, tmp_path) -> None:
        """The checkout directory is cleaned up after the pipeline (success or error)."""
        run = self._make_run_mock()
        repo = self._make_repo_mock()  # has github_repo_id, so mkdtemp will be called

        tmp_str = str(tmp_path)

        with patch("app.runs.service.get_sync_db") as mock_db, \
             patch("tempfile.mkdtemp", return_value=tmp_str), \
             patch("runner.sandbox.checkout.clone_repo"), \
             patch("runner.detector.orchestrator.detect", return_value=_make_detection()), \
             patch("runner.validator.executor.run_baseline", return_value=_make_baseline(is_success=False)), \
             patch("app.runs.service._increment_failure_counter"), \
             patch("shutil.rmtree") as mock_rmtree, \
             patch.object(Path, "exists", return_value=True):

            session = MagicMock()
            session.get.side_effect = lambda m, pk: run if m == Run else (
                repo if m == Repository else _make_settings()
            )
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            # Baseline fails — but cleanup should still happen
            RunService().execute_full_pipeline(str(run.id))

        assert mock_rmtree.called
        called_with = mock_rmtree.call_args[0][0]
        assert str(called_with) == tmp_str

    def test_execute_full_pipeline_run_not_found_raises(self) -> None:
        with patch("app.runs.service.get_sync_db") as mock_db:
            session = MagicMock()
            session.get.return_value = None  # run not found
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            with pytest.raises(ValueError, match="not found"):
                RunService().execute_full_pipeline(str(uuid.uuid4()))


def _make_settings(
    llm_provider="anthropic",
    llm_model="claude-sonnet-4-5",
    max_candidates_per_run=20,
    max_proposals_per_run=10,
):
    s = MagicMock(spec=Settings)
    s.llm_provider = llm_provider
    s.llm_model = llm_model
    s.max_candidates_per_run = max_candidates_per_run
    s.max_proposals_per_run = max_proposals_per_run
    s.paused = False
    s.consecutive_setup_failures = 0
    s.consecutive_flaky_runs = 0
    return s


# ============================================================================
# Phase 17: _build_repo_url
# ============================================================================

class TestBuildRepoUrl:
    """Unit tests for the _build_repo_url helper."""

    def test_prefers_full_name_over_numeric_id(self):
        from app.runs.service import _build_repo_url

        url = _build_repo_url("acme/api-service", 123456)
        assert url == "https://github.com/acme/api-service.git"

    def test_fallback_to_numeric_id(self):
        from app.runs.service import _build_repo_url

        url = _build_repo_url(None, 123456)
        assert "repositories/123456" in url

    def test_raises_when_both_none(self):
        from app.runs.service import _build_repo_url

        with pytest.raises(ValueError, match="neither"):
            _build_repo_url(None, None)

    def test_full_name_only(self):
        from app.runs.service import _build_repo_url

        url = _build_repo_url("org/repo", None)
        assert url == "https://github.com/org/repo.git"


# ============================================================================
# Phase 17: _upload_baseline_artifacts
# ============================================================================

class TestUploadBaselineArtifacts:
    """Tests for the artifact upload helper."""

    def _make_bundle(self, filename="baseline.json", artifact_type="baseline"):
        bundle = MagicMock()
        bundle.filename = filename
        bundle.storage_path = f"repos/r1/runs/r2/{filename}"
        bundle.content = '{"ok": true}'
        bundle.artifact_type = artifact_type
        return bundle

    def test_writes_artifact_records_to_db(self):
        from app.runs.service import _upload_baseline_artifacts

        bundle = self._make_bundle()

        with patch("runner.packaging.bundler.bundle_artifacts", return_value=[bundle]), \
             patch("app.runs.service.get_sync_db") as mock_db_ctx, \
             patch("app.runs.service.get_settings") as mock_settings:

            mock_settings.return_value.supabase_service_key = None  # skip Supabase upload
            session = MagicMock()
            mock_db_ctx.return_value.__enter__ = MagicMock(return_value=session)
            mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

            _upload_baseline_artifacts("run-1", "repo-1", MagicMock())

            session.add.assert_called_once()
            session.commit.assert_called_once()

    def test_does_not_raise_on_bundle_failure(self):
        """Bundling errors must not propagate — the run should continue."""
        from app.runs.service import _upload_baseline_artifacts

        with patch("runner.packaging.bundler.bundle_artifacts", side_effect=RuntimeError("boom")):
            # Must not raise:
            _upload_baseline_artifacts("run-1", "repo-1", MagicMock())

    def test_does_not_raise_on_db_failure(self):
        """DB write errors must not propagate."""
        from app.runs.service import _upload_baseline_artifacts

        bundle = self._make_bundle()

        with patch("runner.packaging.bundler.bundle_artifacts", return_value=[bundle]), \
             patch("app.runs.service.get_sync_db") as mock_db_ctx, \
             patch("app.runs.service.get_settings") as mock_settings:

            mock_settings.return_value.supabase_service_key = None
            mock_db_ctx.side_effect = RuntimeError("db down")

            # Must not raise:
            _upload_baseline_artifacts("run-1", "repo-1", MagicMock())


# ============================================================================
# _build_repo_url — token support for private repos
# ============================================================================

class TestBuildRepoUrlWithToken:
    """Verify _build_repo_url embeds the installation token for private repos."""

    def test_token_embedded_in_url(self):
        from app.runs.service import _build_repo_url

        url = _build_repo_url("acme/private-repo", 99, token="ghs_abc123")
        assert url == "https://x-access-token:ghs_abc123@github.com/acme/private-repo.git"

    def test_no_token_returns_plain_https(self):
        from app.runs.service import _build_repo_url

        url = _build_repo_url("acme/public-repo", 99, token=None)
        assert url == "https://github.com/acme/public-repo.git"
        assert "x-access-token" not in url

    def test_token_none_by_default(self):
        from app.runs.service import _build_repo_url

        url = _build_repo_url("acme/repo", None)
        assert "x-access-token" not in url


# ============================================================================
# _write_proposals_to_db — metrics_after + LLM traces stored
# ============================================================================

class TestWriteProposalsFields:
    """Verify metrics_after and LLM traces are passed to the Proposal constructor."""

    def _make_mock_session(self):
        session = MagicMock()
        captured = []

        def add_side_effect(obj):
            captured.append(obj)

        session.add.side_effect = add_side_effect
        session._captured = captured
        return session

    def _run_write(self, session, n_accepted=1):
        from app.runs.service import _write_proposals_to_db

        run_id = str(uuid.uuid4())
        repo_id = str(uuid.uuid4())

        # Build a cycle with a candidate whose attempt has a pipeline_result
        pipeline_result = MagicMock()
        pipeline_result.to_dict.return_value = {"is_success": True, "p95_ms": 80}

        attempt = MagicMock()
        attempt.pipeline_result = pipeline_result

        candidate = MagicMock()
        candidate.is_accepted = True
        candidate.final_verdict = MagicMock(is_accepted=True, confidence="high")
        candidate.attempts = [attempt]

        trace = _make_thinking_trace()

        opp = MagicMock()
        opp.location = "src/app.ts"
        opp.category = "performance"
        opp.rationale = "Hot path"
        opp.risk_score = 0.2
        opp.thinking_trace = trace

        patch_obj = MagicMock()
        patch_obj.diff = "--- a/src/app.ts\n+++ b/src/app.ts\n@@ -1 +1 @@\n-old\n+new\n"
        patch_obj.thinking_trace = trace

        agent_run = MagicMock()
        agent_run.patches = [patch_obj]

        cycle = MagicMock()
        cycle.candidate_results = [candidate]
        cycle.opportunity_for_candidate = [opp]
        cycle.agent_run = agent_run

        baseline = _make_baseline()

        with patch("app.runs.service.get_sync_db") as mock_db:
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            _write_proposals_to_db(
                run_id=run_id,
                repo_id=repo_id,
                cycle_result=cycle,
                baseline=baseline,
                max_proposals=10,
            )

        return session._captured

    def test_metrics_after_stored_on_proposal(self):
        """The Proposal row receives metrics_after from the last attempt's pipeline_result."""
        session = self._make_mock_session()
        objects = self._run_write(session)

        from app.db.models import Proposal
        proposals = [o for o in objects if isinstance(o, Proposal)]
        assert len(proposals) == 1
        assert proposals[0].metrics_after == {"is_success": True, "p95_ms": 80}

    def test_discovery_trace_stored_on_proposal(self):
        """discovery_trace is populated on the Proposal row."""
        session = self._make_mock_session()
        objects = self._run_write(session)

        from app.db.models import Proposal
        proposals = [o for o in objects if isinstance(o, Proposal)]
        assert len(proposals) == 1
        assert proposals[0].discovery_trace is not None

    def test_patch_trace_stored_on_proposal(self):
        """patch_trace is populated on the Proposal row."""
        session = self._make_mock_session()
        objects = self._run_write(session)

        from app.db.models import Proposal
        proposals = [o for o in objects if isinstance(o, Proposal)]
        assert len(proposals) == 1
        assert proposals[0].patch_trace is not None

    def test_metrics_after_none_when_no_attempts(self):
        """If a candidate has no attempts, metrics_after is None (no crash)."""
        from app.runs.service import _write_proposals_to_db

        run_id = str(uuid.uuid4())
        repo_id = str(uuid.uuid4())

        candidate = MagicMock()
        candidate.is_accepted = True
        candidate.final_verdict = MagicMock(is_accepted=True, confidence="low")
        candidate.attempts = []  # no attempts

        patch_obj = MagicMock()
        patch_obj.diff = "--- a/x.ts\n+++ b/x.ts"
        patch_obj.thinking_trace = None

        opp = MagicMock()
        opp.location = "x.ts:1"
        opp.category = "dead_code"
        opp.rationale = "unused"
        opp.risk_score = 0.1
        opp.thinking_trace = None

        agent_run = MagicMock()
        agent_run.patches = [patch_obj]

        cycle = MagicMock()
        cycle.candidate_results = [candidate]
        cycle.opportunity_for_candidate = [opp]
        cycle.agent_run = agent_run

        captured = []
        session = MagicMock()
        session.add.side_effect = lambda o: captured.append(o)

        with patch("app.runs.service.get_sync_db") as mock_db:
            mock_db.return_value.__enter__ = lambda s: session
            mock_db.return_value.__exit__ = lambda s, *a: None

            _write_proposals_to_db(
                run_id=run_id,
                repo_id=repo_id,
                cycle_result=cycle,
                baseline=_make_baseline(),
                max_proposals=10,
            )

        from app.db.models import Proposal
        proposals = [o for o in captured if isinstance(o, Proposal)]
        assert proposals[0].metrics_after is None
