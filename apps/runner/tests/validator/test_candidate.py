"""Tests for the candidate validation pipeline.

Tests cover:
- Successful patch apply + test pass → accepted
- Test failure on attempt 1 + pass on attempt 2 (flaky rerun)
- Patch apply failure → not accepted, error recorded
- Patch always reverted regardless of outcome
- Attempt records for full traceability
"""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from runner.detector.types import DetectionResult
from runner.patchgen.types import PatchResult
from runner.validator.candidate import run_candidate_validation
from runner.validator.patch_applicator import PatchApplyError
from runner.validator.types import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    BaselineResult,
    StepResult,
)


def _make_config(
    test_cmd: str = "npm test",
    build_cmd: str = None,
    typecheck_cmd: str = None,
    bench_cmd: str = None,
) -> DetectionResult:
    return DetectionResult(
        package_manager="npm",
        install_cmd="npm ci",
        test_cmd=test_cmd,
        build_cmd=build_cmd,
        typecheck_cmd=typecheck_cmd,
        bench_cmd=bench_cmd,
    )


def _make_patch(diff: str = "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-old\n+new\n") -> PatchResult:
    return PatchResult(
        diff=diff,
        explanation="test patch",
        touched_files=["src/f.ts"],
        template_name="set_membership",
        lines_changed=2,
    )


def _make_passing_pipeline(has_bench: bool = False) -> BaselineResult:
    r = BaselineResult()
    r.steps = [StepResult("test", "npm test", 0, 0.5, "ok", "")]
    r.is_success = True
    if has_bench:
        r.bench_result = {"command": "bench", "duration_seconds": 0.9, "stdout": ""}
    return r


def _make_failing_pipeline() -> BaselineResult:
    r = BaselineResult()
    r.steps = [StepResult("test", "npm test", 1, 0.5, "", "FAIL")]
    r.is_success = False
    return r


def _make_baseline(has_bench: bool = False) -> BaselineResult:
    r = BaselineResult(is_success=True)
    if has_bench:
        r.bench_result = {"command": "bench", "duration_seconds": 1.0, "stdout": ""}
    return r


class TestSuccessfulValidation:
    def test_accepts_when_tests_pass(self, tmp_path):
        with (
            patch("runner.validator.candidate.apply_diff"),
            patch("runner.validator.candidate.revert_diff"),
            patch(
                "runner.validator.candidate._run_candidate_pipeline",
                return_value=_make_passing_pipeline(),
            ),
        ):
            result = run_candidate_validation(
                repo_dir=tmp_path,
                config=_make_config(),
                patch=_make_patch(),
                baseline=_make_baseline(),
            )

        assert result.is_accepted is True
        assert len(result.attempts) == 1
        assert result.attempts[0].patch_applied is True
        assert result.final_verdict is not None
        assert result.final_verdict.confidence == CONFIDENCE_MEDIUM

    def test_high_confidence_with_benchmark(self, tmp_path):
        with (
            patch("runner.validator.candidate.apply_diff"),
            patch("runner.validator.candidate.revert_diff"),
            patch(
                "runner.validator.candidate._run_candidate_pipeline",
                return_value=_make_passing_pipeline(has_bench=True),
            ),
        ):
            result = run_candidate_validation(
                repo_dir=tmp_path,
                config=_make_config(bench_cmd="npm run bench"),
                patch=_make_patch(),
                baseline=_make_baseline(has_bench=True),
            )

        assert result.is_accepted is True
        assert result.final_verdict.confidence == CONFIDENCE_HIGH


class TestFlakyTestRerun:
    def test_rerun_on_test_failure(self, tmp_path):
        """Attempt 1 fails → attempt 2 passes → accepted."""
        call_count = {"n": 0}

        def mock_pipeline(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _make_failing_pipeline()
            return _make_passing_pipeline()

        with (
            patch("runner.validator.candidate.apply_diff"),
            patch("runner.validator.candidate.revert_diff"),
            patch("runner.validator.candidate._run_candidate_pipeline", side_effect=mock_pipeline),
        ):
            result = run_candidate_validation(
                repo_dir=tmp_path,
                config=_make_config(),
                patch=_make_patch(),
                baseline=_make_baseline(),
            )

        assert len(result.attempts) == 2
        assert result.attempts[0].verdict.is_accepted is False
        assert result.attempts[1].verdict.is_accepted is True
        assert result.is_accepted is True

    def test_rejects_when_both_attempts_fail(self, tmp_path):
        """Both attempts fail → rejected, 2 attempts recorded."""
        with (
            patch("runner.validator.candidate.apply_diff"),
            patch("runner.validator.candidate.revert_diff"),
            patch(
                "runner.validator.candidate._run_candidate_pipeline",
                return_value=_make_failing_pipeline(),
            ),
        ):
            result = run_candidate_validation(
                repo_dir=tmp_path,
                config=_make_config(),
                patch=_make_patch(),
                baseline=_make_baseline(),
            )

        assert len(result.attempts) == 2
        assert result.is_accepted is False

    def test_no_rerun_when_tests_pass_on_first(self, tmp_path):
        """Only one attempt when tests pass."""
        with (
            patch("runner.validator.candidate.apply_diff"),
            patch("runner.validator.candidate.revert_diff"),
            patch(
                "runner.validator.candidate._run_candidate_pipeline",
                return_value=_make_passing_pipeline(),
            ),
        ):
            result = run_candidate_validation(
                repo_dir=tmp_path,
                config=_make_config(),
                patch=_make_patch(),
                baseline=_make_baseline(),
            )

        assert len(result.attempts) == 1


class TestPatchApplyFailure:
    def test_error_recorded_on_apply_failure(self, tmp_path):
        with patch(
            "runner.validator.candidate.apply_diff",
            side_effect=PatchApplyError("patch failed"),
        ):
            result = run_candidate_validation(
                repo_dir=tmp_path,
                config=_make_config(),
                patch=_make_patch(),
                baseline=_make_baseline(),
            )

        assert result.is_accepted is False
        assert result.attempts[0].patch_applied is False
        assert result.attempts[0].error is not None
        assert "Patch apply error" in result.attempts[0].error

    def test_verdict_is_none_when_apply_fails(self, tmp_path):
        with patch(
            "runner.validator.candidate.apply_diff",
            side_effect=PatchApplyError("patch failed"),
        ):
            result = run_candidate_validation(
                repo_dir=tmp_path,
                config=_make_config(),
                patch=_make_patch(),
                baseline=_make_baseline(),
            )

        # No pipeline ran, so no verdict
        assert result.attempts[0].verdict is None
        assert result.final_verdict is None


class TestPatchAlwaysReverted:
    def test_revert_called_even_on_test_failure(self, tmp_path):
        revert_mock = MagicMock()

        with (
            patch("runner.validator.candidate.apply_diff"),
            patch("runner.validator.candidate.revert_diff", revert_mock),
            patch(
                "runner.validator.candidate._run_candidate_pipeline",
                return_value=_make_failing_pipeline(),
            ),
        ):
            run_candidate_validation(
                repo_dir=tmp_path,
                config=_make_config(),
                patch=_make_patch(),
                baseline=_make_baseline(),
            )

        # 2 attempts (flaky rerun) → 2 reverts
        assert revert_mock.call_count == 2

    def test_revert_called_even_on_pipeline_exception(self, tmp_path):
        revert_mock = MagicMock()

        with (
            patch("runner.validator.candidate.apply_diff"),
            patch("runner.validator.candidate.revert_diff", revert_mock),
            patch(
                "runner.validator.candidate._run_candidate_pipeline",
                side_effect=RuntimeError("unexpected"),
            ),
        ):
            result = run_candidate_validation(
                repo_dir=tmp_path,
                config=_make_config(),
                patch=_make_patch(),
                baseline=_make_baseline(),
            )

        assert revert_mock.call_count >= 1
        assert result.is_accepted is False


class TestAttemptRecordSerialization:
    def test_attempt_to_dict_contains_all_fields(self, tmp_path):
        with (
            patch("runner.validator.candidate.apply_diff"),
            patch("runner.validator.candidate.revert_diff"),
            patch(
                "runner.validator.candidate._run_candidate_pipeline",
                return_value=_make_passing_pipeline(),
            ),
        ):
            result = run_candidate_validation(
                repo_dir=tmp_path,
                config=_make_config(),
                patch=_make_patch(),
                baseline=_make_baseline(),
            )

        d = result.attempts[0].to_dict()
        assert all(k in d for k in [
            "attempt_number", "patch_applied",
            "pipeline_result", "verdict", "error", "timestamp",
        ])

    def test_candidate_result_to_dict(self, tmp_path):
        with (
            patch("runner.validator.candidate.apply_diff"),
            patch("runner.validator.candidate.revert_diff"),
            patch(
                "runner.validator.candidate._run_candidate_pipeline",
                return_value=_make_passing_pipeline(),
            ),
        ):
            result = run_candidate_validation(
                repo_dir=tmp_path,
                config=_make_config(),
                patch=_make_patch(),
                baseline=_make_baseline(),
            )

        d = result.to_dict()
        assert "attempts" in d
        assert "final_verdict" in d
        assert "is_accepted" in d
