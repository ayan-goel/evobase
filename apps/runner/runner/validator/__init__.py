"""Validator module for baseline and candidate execution.

Public API:
    run_baseline(repo_dir, config) -> BaselineResult
    run_step(name, command, cwd) -> StepResult
    run_candidate_validation(repo_dir, config, patch, baseline) -> CandidateResult
    evaluate_acceptance(candidate_result, baseline_result) -> AcceptanceVerdict
    compare_benchmarks(baseline, candidate) -> Optional[BenchmarkComparison]
"""

from runner.validator.acceptance import compare_benchmarks, evaluate_acceptance
from runner.validator.candidate import run_candidate_validation
from runner.validator.executor import run_baseline, run_step
from runner.validator.patch_applicator import PatchApplyError, apply_diff, revert_diff
from runner.validator.types import (
    AcceptanceVerdict,
    AttemptRecord,
    BaselineResult,
    BenchmarkComparison,
    CandidateResult,
    PipelineError,
    StepResult,
)

__all__ = [
    "run_baseline",
    "run_step",
    "run_candidate_validation",
    "evaluate_acceptance",
    "compare_benchmarks",
    "apply_diff",
    "revert_diff",
    "PatchApplyError",
    "AcceptanceVerdict",
    "AttemptRecord",
    "BaselineResult",
    "BenchmarkComparison",
    "CandidateResult",
    "PipelineError",
    "StepResult",
]
