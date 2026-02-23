"""Validator module for baseline and candidate execution.

This package intentionally avoids eager imports of executor/candidate modules
to prevent circular-import issues with the execution strategy layer.
"""

from runner.validator.types import (
    AcceptanceVerdict,
    AttemptRecord,
    BaselineResult,
    BenchmarkComparison,
    CandidateResult,
    PipelineError,
    StepResult,
)
from runner.validator.patch_applicator import PatchApplyError


def run_baseline(*args, **kwargs):
    from runner.validator.executor import run_baseline as _run_baseline

    return _run_baseline(*args, **kwargs)


def run_step(*args, **kwargs):
    from runner.validator.executor import run_step as _run_step

    return _run_step(*args, **kwargs)


def run_candidate_validation(*args, **kwargs):
    from runner.validator.candidate import run_candidate_validation as _run_candidate_validation

    return _run_candidate_validation(*args, **kwargs)


def evaluate_acceptance(*args, **kwargs):
    from runner.validator.acceptance import evaluate_acceptance as _evaluate_acceptance

    return _evaluate_acceptance(*args, **kwargs)


def compare_benchmarks(*args, **kwargs):
    from runner.validator.acceptance import compare_benchmarks as _compare_benchmarks

    return _compare_benchmarks(*args, **kwargs)


def apply_diff(*args, **kwargs):
    from runner.validator.patch_applicator import apply_diff as _apply_diff

    return _apply_diff(*args, **kwargs)


def revert_diff(*args, **kwargs):
    from runner.validator.patch_applicator import revert_diff as _revert_diff

    return _revert_diff(*args, **kwargs)

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
