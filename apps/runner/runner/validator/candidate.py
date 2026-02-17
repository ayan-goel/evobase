"""Candidate validation pipeline.

Orchestrates the full apply → run → evaluate → revert cycle for a
single patch candidate.

Flow:
  1. Apply the patch diff to the repo
  2. Re-run the pipeline (skip install; re-use baseline's install step)
  3. If tests fail, rerun the test step once (flaky test handling)
  4. Evaluate acceptance gates
  5. Revert the patch (always, regardless of outcome)

All attempts are recorded so the full trace is available for proposal
packaging in Phase 10.
"""

import logging
from pathlib import Path
from typing import Optional

from runner.detector.types import DetectionResult
from runner.patchgen.types import PatchResult
from runner.validator.acceptance import evaluate_acceptance
from runner.validator.executor import run_step
from runner.validator.patch_applicator import PatchApplyError, apply_diff, revert_diff
from runner.validator.types import (
    AttemptRecord,
    BaselineResult,
    CandidateResult,
    StepResult,
)

logger = logging.getLogger(__name__)

# Default timeout for candidate pipeline steps (seconds)
CANDIDATE_STEP_TIMEOUT = 300


def run_candidate_validation(
    repo_dir: Path,
    config: DetectionResult,
    patch: PatchResult,
    baseline: BaselineResult,
) -> CandidateResult:
    """Validate a patch candidate against the baseline.

    Applies the patch, runs build/typecheck/test, evaluates acceptance,
    then reverts — recording all attempts for evidence.

    Returns a CandidateResult with all attempt records and the final verdict.
    The patch is always reverted; the caller may re-apply if accepted.
    """
    result = CandidateResult()

    # Attempt 1
    attempt1 = _run_single_attempt(
        attempt_number=1,
        repo_dir=repo_dir,
        config=config,
        patch=patch,
        baseline=baseline,
    )
    result.attempts.append(attempt1)

    # Flaky test handling: if tests failed on attempt 1, rerun once
    if attempt1.pipeline_result and _tests_failed(attempt1.pipeline_result):
        logger.info(
            "Tests failed on attempt 1; running flaky rerun (attempt 2)"
        )
        attempt2 = _run_single_attempt(
            attempt_number=2,
            repo_dir=repo_dir,
            config=config,
            patch=patch,
            baseline=baseline,
        )
        result.attempts.append(attempt2)
        decisive_attempt = attempt2
    else:
        decisive_attempt = attempt1

    result.final_verdict = decisive_attempt.verdict
    result.is_accepted = (
        decisive_attempt.verdict.is_accepted
        if decisive_attempt.verdict
        else False
    )

    logger.info(
        "Candidate validation complete: accepted=%s confidence=%s",
        result.is_accepted,
        result.final_verdict.confidence if result.final_verdict else "n/a",
    )

    return result


def _run_single_attempt(
    attempt_number: int,
    repo_dir: Path,
    config: DetectionResult,
    patch: PatchResult,
    baseline: BaselineResult,
) -> AttemptRecord:
    """Execute one validation attempt and return the full record.

    Always reverts the patch before returning, even on error.
    """
    patch_applied = False
    pipeline_result: Optional[BaselineResult] = None
    error: Optional[str] = None

    try:
        apply_diff(repo_dir, patch.diff)
        patch_applied = True

        pipeline_result = _run_candidate_pipeline(repo_dir, config, baseline)

    except PatchApplyError as exc:
        logger.error("Attempt %d: patch apply failed: %s", attempt_number, exc)
        error = f"Patch apply error: {exc}"

    except Exception as exc:
        logger.error("Attempt %d: unexpected error: %s", attempt_number, exc)
        error = str(exc)

    finally:
        if patch_applied:
            try:
                revert_diff(repo_dir, patch.diff)
            except PatchApplyError as exc:
                logger.error(
                    "Attempt %d: patch revert failed (repo may be dirty): %s",
                    attempt_number, exc,
                )

    # Evaluate verdict from pipeline results
    verdict = None
    if pipeline_result is not None:
        verdict = evaluate_acceptance(pipeline_result, baseline)

    return AttemptRecord(
        attempt_number=attempt_number,
        patch_applied=patch_applied,
        pipeline_result=pipeline_result,
        verdict=verdict,
        error=error,
    )


def _run_candidate_pipeline(
    repo_dir: Path,
    config: DetectionResult,
    baseline: BaselineResult,
) -> BaselineResult:
    """Run build/typecheck/test on the patched repo.

    Skips install — the baseline already installed dependencies and
    the patch only touches source files (enforced by constraints).
    Re-runs bench if the baseline had bench data, for comparison.
    """
    result = BaselineResult()

    try:
        # Build (optional — same as baseline)
        if config.build_cmd:
            build_step = run_step(
                "build", config.build_cmd, repo_dir,
                timeout=CANDIDATE_STEP_TIMEOUT,
            )
            result.steps.append(build_step)
            if not build_step.is_success:
                logger.warning("Candidate build failed (non-critical); continuing")

        # Typecheck (optional)
        if config.typecheck_cmd:
            typecheck_step = run_step(
                "typecheck", config.typecheck_cmd, repo_dir,
                timeout=CANDIDATE_STEP_TIMEOUT,
            )
            result.steps.append(typecheck_step)
            if not typecheck_step.is_success:
                logger.warning("Candidate typecheck failed; confidence will be low")

        # Test (required for acceptance)
        if config.test_cmd:
            test_step = run_step(
                "test", config.test_cmd, repo_dir,
                timeout=CANDIDATE_STEP_TIMEOUT,
            )
            result.steps.append(test_step)

        # Bench (only if baseline had bench data, for fair comparison)
        if baseline.bench_result and config.bench_cmd:
            bench_step = run_step(
                "bench", config.bench_cmd, repo_dir,
                timeout=CANDIDATE_STEP_TIMEOUT,
            )
            result.steps.append(bench_step)
            if bench_step.is_success:
                result.bench_result = {
                    "command": config.bench_cmd,
                    "stdout": bench_step.stdout,
                    "duration_seconds": bench_step.duration_seconds,
                }

        result.is_success = _all_critical_steps_passed(result)

    except Exception as exc:
        result.is_success = False
        result.error = str(exc)
        logger.error("Candidate pipeline raised: %s", exc)

    return result


def _tests_failed(pipeline_result: BaselineResult) -> bool:
    """Return True if the test step ran and failed."""
    test_step = next(
        (s for s in pipeline_result.steps if s.name == "test"),
        None,
    )
    return test_step is not None and not test_step.is_success


def _all_critical_steps_passed(pipeline_result: BaselineResult) -> bool:
    """Return True if no critical step (test) failed."""
    test_step = next(
        (s for s in pipeline_result.steps if s.name == "test"),
        None,
    )
    if test_step is not None and not test_step.is_success:
        return False
    return True
