"""Tests for the proposal bundler.

Covers:
- Bundle produces exactly 3 artifacts (proposal.json, diff.patch, trace.json)
- proposal.json shape: all required top-level keys present
- Proposal summary is non-empty
- metrics_before / metrics_after extraction
- Trace timeline includes all attempts
- Non-accepted candidate still bundles (for debugging)
- Storage paths follow expected convention
"""

import json
from datetime import datetime, timezone

import pytest

from runner.packaging.proposal_bundler import (
    PROPOSAL_SCHEMA_VERSION,
    bundle_proposal,
    extract_metrics,
)
from runner.patchgen.types import PatchResult
from runner.scanner.types import Opportunity
from runner.validator.types import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    AcceptanceVerdict,
    AttemptRecord,
    BaselineResult,
    BenchmarkComparison,
    CandidateResult,
    StepResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_opportunity() -> Opportunity:
    return Opportunity(
        type="set_membership",
        location="src/utils.ts:42",
        rationale="arr.indexOf(x) !== -1 should use includes()",
        risk_score=0.2,
        source="heuristic",
    )


def _make_patch() -> PatchResult:
    return PatchResult(
        diff="--- a/src/utils.ts\n+++ b/src/utils.ts\n@@ -42 +42 @@\n-old\n+new\n",
        explanation="Replaced Array.indexOf() membership check with Array.includes().",
        touched_files=["src/utils.ts"],
        template_name="set_membership",
        lines_changed=2,
    )


def _make_step(name: str, exit_code: int = 0, duration: float = 1.0) -> StepResult:
    return StepResult(name=name, command=f"run {name}", exit_code=exit_code,
                      duration_seconds=duration, stdout="ok", stderr="")


def _make_baseline() -> BaselineResult:
    r = BaselineResult(is_success=True)
    r.steps = [_make_step("install"), _make_step("test")]
    r.bench_result = {"command": "bench", "duration_seconds": 1.0, "stdout": ""}
    return r


def _make_candidate(accepted: bool = True) -> CandidateResult:
    pipeline = BaselineResult(is_success=accepted)
    pipeline.steps = [_make_step("test", exit_code=0 if accepted else 1)]
    if accepted:
        pipeline.bench_result = {"command": "bench", "duration_seconds": 0.9, "stdout": ""}

    verdict = AcceptanceVerdict(
        is_accepted=accepted,
        confidence=CONFIDENCE_HIGH if accepted else "low",
        reason="Tests pass and benchmark improves" if accepted else "Tests failed",
        gates_passed=["test_gate", "benchmark_gate"] if accepted else [],
        gates_failed=[] if accepted else ["test_gate"],
        benchmark_comparison=BenchmarkComparison(
            baseline_duration_seconds=1.0,
            candidate_duration_seconds=0.9,
            improvement_pct=10.0,
            is_significant=True,
            passes_threshold=True,
        ) if accepted else None,
    )

    attempt = AttemptRecord(
        attempt_number=1,
        patch_applied=True,
        pipeline_result=pipeline,
        verdict=verdict,
    )

    return CandidateResult(
        attempts=[attempt],
        final_verdict=verdict,
        is_accepted=accepted,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBundleProposalArtifactCount:
    def test_produces_exactly_three_bundles(self):
        bundles = bundle_proposal(
            run_id="run-123",
            repo_id="repo-456",
            opportunity=_make_opportunity(),
            patch=_make_patch(),
            baseline=_make_baseline(),
            candidate=_make_candidate(),
        )
        assert len(bundles) == 3

    def test_bundle_filenames(self):
        bundles = bundle_proposal(
            run_id="r", repo_id="rp",
            opportunity=_make_opportunity(), patch=_make_patch(),
            baseline=_make_baseline(), candidate=_make_candidate(),
        )
        filenames = {b.filename for b in bundles}
        assert filenames == {"proposal.json", "diff.patch", "trace.json"}

    def test_artifact_types(self):
        bundles = bundle_proposal(
            run_id="r", repo_id="rp",
            opportunity=_make_opportunity(), patch=_make_patch(),
            baseline=_make_baseline(), candidate=_make_candidate(),
        )
        types = {b.artifact_type for b in bundles}
        assert types == {"proposal", "diff", "trace"}

    def test_storage_paths_follow_convention(self):
        bundles = bundle_proposal(
            run_id="run-123", repo_id="repo-456",
            opportunity=_make_opportunity(), patch=_make_patch(),
            baseline=_make_baseline(), candidate=_make_candidate(),
        )
        for bundle in bundles:
            assert bundle.storage_path.startswith("repos/repo-456/runs/run-123/")


class TestProposalJsonSchema:
    def setup_method(self):
        bundles = bundle_proposal(
            run_id="run-123", repo_id="repo-456",
            opportunity=_make_opportunity(), patch=_make_patch(),
            baseline=_make_baseline(), candidate=_make_candidate(),
        )
        proposal_bundle = next(b for b in bundles if b.filename == "proposal.json")
        self.data = json.loads(proposal_bundle.content)

    def test_schema_version_present(self):
        assert self.data["schema_version"] == PROPOSAL_SCHEMA_VERSION

    def test_run_and_repo_ids(self):
        assert self.data["run_id"] == "run-123"
        assert self.data["repo_id"] == "repo-456"

    def test_opportunity_field(self):
        opp = self.data["opportunity"]
        assert opp["type"] == "set_membership"
        assert opp["location"] == "src/utils.ts:42"
        assert "risk_score" in opp

    def test_patch_field(self):
        patch = self.data["patch"]
        assert patch["template_name"] == "set_membership"
        assert patch["touched_files"] == ["src/utils.ts"]
        assert patch["lines_changed"] == 2
        assert "explanation" in patch
        assert "diff_preview" in patch

    def test_summary_non_empty(self):
        assert self.data["summary"]
        assert len(self.data["summary"]) > 5

    def test_confidence_field(self):
        assert self.data["confidence"] == CONFIDENCE_HIGH

    def test_is_accepted_true(self):
        assert self.data["is_accepted"] is True

    def test_acceptance_verdict(self):
        verdict = self.data["acceptance_verdict"]
        assert verdict["is_accepted"] is True
        assert verdict["confidence"] == CONFIDENCE_HIGH
        assert "benchmark_comparison" in verdict

    def test_metrics_before_shape(self):
        metrics = self.data["metrics_before"]
        assert isinstance(metrics["is_success"], bool)
        assert isinstance(metrics["total_duration_seconds"], float)
        assert isinstance(metrics["steps"], list)

    def test_metrics_after_shape(self):
        metrics = self.data["metrics_after"]
        assert isinstance(metrics["steps"], list)

    def test_trace_timeline_list(self):
        trace = self.data["trace_timeline"]
        assert isinstance(trace, list)
        assert len(trace) == 1
        assert trace[0]["attempt_number"] == 1

    def test_created_at_is_iso_string(self):
        ts = self.data["created_at"]
        datetime.fromisoformat(ts)  # should not raise


class TestDiffPatchArtifact:
    def test_diff_content_matches_patch(self):
        patch = _make_patch()
        bundles = bundle_proposal(
            run_id="r", repo_id="rp",
            opportunity=_make_opportunity(), patch=patch,
            baseline=_make_baseline(), candidate=_make_candidate(),
        )
        diff_bundle = next(b for b in bundles if b.filename == "diff.patch")
        assert diff_bundle.content == patch.diff

    def test_diff_preview_truncated_for_large_diffs(self):
        long_diff = "x" * 600
        patch = PatchResult(
            diff=long_diff, explanation="test",
            touched_files=["f.ts"], template_name="t", lines_changed=1,
        )
        bundles = bundle_proposal(
            run_id="r", repo_id="rp",
            opportunity=_make_opportunity(), patch=patch,
            baseline=_make_baseline(), candidate=_make_candidate(),
        )
        proposal_data = json.loads(
            next(b for b in bundles if b.filename == "proposal.json").content
        )
        assert proposal_data["patch"]["diff_preview"].endswith("...")


class TestTraceJsonSchema:
    def setup_method(self):
        bundles = bundle_proposal(
            run_id="run-123", repo_id="repo-456",
            opportunity=_make_opportunity(), patch=_make_patch(),
            baseline=_make_baseline(), candidate=_make_candidate(),
        )
        trace_bundle = next(b for b in bundles if b.filename == "trace.json")
        self.data = json.loads(trace_bundle.content)

    def test_top_level_keys(self):
        assert all(k in self.data for k in [
            "schema_version", "run_id", "repo_id",
            "opportunity_type", "opportunity_location",
            "template_name", "total_attempts",
            "is_accepted", "final_verdict", "attempts",
        ])

    def test_attempt_entries(self):
        assert len(self.data["attempts"]) == 1
        attempt = self.data["attempts"][0]
        assert all(k in attempt for k in [
            "attempt_number", "patch_applied",
            "timestamp", "error", "steps", "verdict",
        ])

    def test_final_verdict_present(self):
        assert self.data["final_verdict"]["is_accepted"] is True

    def test_two_attempts_for_flaky_rerun(self):
        candidate = _make_candidate(accepted=True)
        # Add a second attempt (simulates flaky rerun)
        candidate.attempts.insert(0, AttemptRecord(
            attempt_number=1,
            patch_applied=True,
            pipeline_result=BaselineResult(),
            verdict=AcceptanceVerdict(
                is_accepted=False, confidence="low",
                reason="Tests failed", gates_passed=[], gates_failed=["test_gate"],
            ),
        ))
        candidate.attempts[1] = AttemptRecord(
            attempt_number=2,
            patch_applied=True,
            pipeline_result=candidate.attempts[0].pipeline_result,
            verdict=candidate.final_verdict,
        )

        bundles = bundle_proposal(
            run_id="r", repo_id="rp",
            opportunity=_make_opportunity(), patch=_make_patch(),
            baseline=_make_baseline(), candidate=candidate,
        )
        trace = json.loads(
            next(b for b in bundles if b.filename == "trace.json").content
        )
        assert trace["total_attempts"] == 2


class TestExtractMetrics:
    def test_extracts_all_fields(self):
        r = _make_baseline()
        m = extract_metrics(r)
        assert m["is_success"] is True
        assert m["step_count"] == 2
        assert m["total_duration_seconds"] > 0
        assert len(m["steps"]) == 2
        assert m["bench_result"] is not None

    def test_steps_have_required_keys(self):
        r = _make_baseline()
        m = extract_metrics(r)
        for step in m["steps"]:
            assert all(k in step for k in ["name", "exit_code", "duration_seconds", "is_success"])

    def test_non_accepted_candidate_bundles_anyway(self):
        bundles = bundle_proposal(
            run_id="r", repo_id="rp",
            opportunity=_make_opportunity(), patch=_make_patch(),
            baseline=_make_baseline(), candidate=_make_candidate(accepted=False),
        )
        assert len(bundles) == 3
        proposal_data = json.loads(
            next(b for b in bundles if b.filename == "proposal.json").content
        )
        assert proposal_data["is_accepted"] is False
