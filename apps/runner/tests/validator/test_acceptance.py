"""Tests for acceptance gates and verdict logic."""

import pytest

from runner.validator.acceptance import compare_benchmarks, evaluate_acceptance
from runner.validator.types import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    AcceptanceVerdict,
    BaselineResult,
    BenchmarkComparison,
    StepResult,
)


def _make_step(name: str, exit_code: int = 0) -> StepResult:
    return StepResult(
        name=name,
        command=f"run {name}",
        exit_code=exit_code,
        duration_seconds=0.5,
        stdout="ok",
    )


def _make_baseline(
    has_bench: bool = False,
    bench_duration: float = 1.0,
) -> BaselineResult:
    r = BaselineResult(is_success=True)
    if has_bench:
        r.bench_result = {"command": "bench", "duration_seconds": bench_duration, "stdout": ""}
    return r


def _make_candidate(
    test_passes: bool = True,
    typecheck_passes: bool = True,
    has_typecheck: bool = False,
    has_bench: bool = False,
    bench_duration: float = 0.9,
) -> BaselineResult:
    r = BaselineResult()
    r.steps.append(_make_step("test", exit_code=0 if test_passes else 1))
    if has_typecheck:
        r.steps.append(_make_step("typecheck", exit_code=0 if typecheck_passes else 1))
    if has_bench:
        r.bench_result = {"command": "bench", "duration_seconds": bench_duration, "stdout": ""}
    r.is_success = test_passes
    return r


class TestTestGate:
    def test_tests_pass_accepts(self):
        candidate = _make_candidate(test_passes=True)
        baseline = _make_baseline()
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.is_accepted is True
        assert "test_gate" in verdict.gates_passed

    def test_tests_fail_rejects(self):
        candidate = _make_candidate(test_passes=False)
        baseline = _make_baseline()
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.is_accepted is False
        assert "test_gate" in verdict.gates_failed

    def test_no_test_step_rejects(self):
        candidate = BaselineResult()  # No steps at all
        baseline = _make_baseline()
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.is_accepted is False
        assert "test_gate" in verdict.gates_failed

    def test_rejection_reason_mentions_tests(self):
        candidate = _make_candidate(test_passes=False)
        baseline = _make_baseline()
        verdict = evaluate_acceptance(candidate, baseline)
        assert "test" in verdict.reason.lower() or "Test" in verdict.reason


class TestTypecheckGate:
    def test_typecheck_pass_adds_gate(self):
        candidate = _make_candidate(has_typecheck=True, typecheck_passes=True)
        baseline = _make_baseline()
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.is_accepted is True
        assert "typecheck_gate" in verdict.gates_passed

    def test_typecheck_fail_downgrades_to_low(self):
        candidate = _make_candidate(has_typecheck=True, typecheck_passes=False)
        baseline = _make_baseline()
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.is_accepted is True  # not rejected — still accepted
        assert verdict.confidence == CONFIDENCE_LOW
        assert "typecheck_gate" in verdict.gates_failed

    def test_no_typecheck_is_medium_confidence(self):
        candidate = _make_candidate(has_typecheck=False)
        baseline = _make_baseline()
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.confidence == CONFIDENCE_MEDIUM


class TestBenchmarkGate:
    def test_large_improvement_gives_high_confidence(self):
        candidate = _make_candidate(has_bench=True, bench_duration=0.9)
        baseline = _make_baseline(has_bench=True, bench_duration=1.0)
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.is_accepted is True
        assert verdict.confidence == CONFIDENCE_HIGH
        assert "benchmark_gate" in verdict.gates_passed

    def test_regression_rejects(self):
        candidate = _make_candidate(has_bench=True, bench_duration=1.2)
        baseline = _make_baseline(has_bench=True, bench_duration=1.0)
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.is_accepted is False
        assert "benchmark_gate" in verdict.gates_failed
        assert "regression" in verdict.reason.lower() or "slower" in verdict.reason.lower()

    def test_small_improvement_below_threshold_gives_medium(self):
        # 1% improvement — below 3% threshold
        candidate = _make_candidate(has_bench=True, bench_duration=0.99)
        baseline = _make_baseline(has_bench=True, bench_duration=1.0)
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.is_accepted is True
        assert verdict.confidence == CONFIDENCE_MEDIUM  # below threshold, treated as no bench

    def test_exactly_3pct_improvement_gives_high(self):
        candidate = _make_candidate(has_bench=True, bench_duration=0.97)
        baseline = _make_baseline(has_bench=True, bench_duration=1.0)
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.confidence == CONFIDENCE_HIGH

    def test_no_baseline_bench_gives_medium(self):
        candidate = _make_candidate(has_bench=True)
        baseline = _make_baseline(has_bench=False)
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.confidence == CONFIDENCE_MEDIUM

    def test_benchmark_comparison_included_in_verdict(self):
        candidate = _make_candidate(has_bench=True, bench_duration=0.9)
        baseline = _make_baseline(has_bench=True, bench_duration=1.0)
        verdict = evaluate_acceptance(candidate, baseline)
        assert verdict.benchmark_comparison is not None
        assert verdict.benchmark_comparison.improvement_pct > 0


class TestCompareBenchmarks:
    def test_computes_improvement(self):
        baseline = _make_baseline(has_bench=True, bench_duration=1.0)
        candidate = _make_candidate(has_bench=True, bench_duration=0.9)
        cmp = compare_benchmarks(baseline, candidate)
        assert cmp is not None
        assert abs(cmp.improvement_pct - 10.0) < 0.01
        assert cmp.passes_threshold is True
        assert cmp.is_significant is True

    def test_regression_negative_improvement(self):
        baseline = _make_baseline(has_bench=True, bench_duration=1.0)
        candidate = _make_candidate(has_bench=True, bench_duration=1.1)
        cmp = compare_benchmarks(baseline, candidate)
        assert cmp is not None
        assert cmp.improvement_pct < 0
        assert cmp.passes_threshold is False

    def test_returns_none_when_no_baseline_bench(self):
        baseline = _make_baseline(has_bench=False)
        candidate = _make_candidate(has_bench=True)
        assert compare_benchmarks(baseline, candidate) is None

    def test_returns_none_when_no_candidate_bench(self):
        baseline = _make_baseline(has_bench=True)
        candidate = _make_candidate(has_bench=False)
        assert compare_benchmarks(baseline, candidate) is None

    def test_to_dict_contains_all_fields(self):
        baseline = _make_baseline(has_bench=True, bench_duration=1.0)
        candidate = _make_candidate(has_bench=True, bench_duration=0.9)
        cmp = compare_benchmarks(baseline, candidate)
        d = cmp.to_dict()
        assert all(k in d for k in [
            "baseline_duration_seconds",
            "candidate_duration_seconds",
            "improvement_pct",
            "is_significant",
            "passes_threshold",
        ])


class TestAcceptanceVerdictSerialization:
    def test_to_dict_contains_all_fields(self):
        candidate = _make_candidate(test_passes=True)
        baseline = _make_baseline()
        verdict = evaluate_acceptance(candidate, baseline)
        d = verdict.to_dict()
        assert all(k in d for k in [
            "is_accepted", "confidence", "reason",
            "gates_passed", "gates_failed", "benchmark_comparison",
        ])
