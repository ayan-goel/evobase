"""Acceptance logic for candidate patches.

Gates (in order of application):
  1. test_gate — candidate tests must pass (always required)
  2. typecheck_gate — candidate typecheck must pass (if available; failure
                      downgrades confidence to "low" but does not reject)
  3. benchmark_gate — if baseline has bench data, candidate must show
                      ≥3% improvement beyond noise (rejects if it regresses)

Confidence levels:
  high   — tests pass + benchmark shows ≥3% improvement
  medium — tests pass + no benchmark available (tech debt safe)
  low    — tests pass + typecheck failed (PR created but flagged disabled)
"""

import logging
from typing import Optional

from runner.validator.types import (
    BENCHMARK_MIN_IMPROVEMENT_PCT,
    BENCHMARK_NOISE_THRESHOLD_PCT,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    AcceptanceVerdict,
    BaselineResult,
    BenchmarkComparison,
)

logger = logging.getLogger(__name__)


def compare_benchmarks(
    baseline: BaselineResult,
    candidate: BaselineResult,
) -> Optional[BenchmarkComparison]:
    """Compare benchmark timing from baseline vs candidate runs.

    Returns None if either run lacks benchmark data.
    """
    if not baseline.bench_result or not candidate.bench_result:
        return None

    baseline_dur = baseline.bench_result.get("duration_seconds")
    candidate_dur = candidate.bench_result.get("duration_seconds")

    if baseline_dur is None or candidate_dur is None or baseline_dur <= 0:
        return None

    improvement_pct = (baseline_dur - candidate_dur) / baseline_dur * 100
    is_significant = improvement_pct > BENCHMARK_NOISE_THRESHOLD_PCT
    passes_threshold = improvement_pct >= BENCHMARK_MIN_IMPROVEMENT_PCT

    logger.debug(
        "Benchmark comparison: baseline=%.3fs candidate=%.3fs improvement=%.2f%%",
        baseline_dur, candidate_dur, improvement_pct,
    )

    return BenchmarkComparison(
        baseline_duration_seconds=baseline_dur,
        candidate_duration_seconds=candidate_dur,
        improvement_pct=improvement_pct,
        is_significant=is_significant,
        passes_threshold=passes_threshold,
    )


def evaluate_acceptance(
    candidate_result: BaselineResult,
    baseline_result: BaselineResult,
) -> AcceptanceVerdict:
    """Apply all acceptance gates and return the final verdict.

    Gate 1 (test_gate) is hard: failure rejects immediately.
    Gate 2 (typecheck_gate) is soft: failure downgrades confidence.
    Gate 3 (benchmark_gate) is conditional: only applied when both runs
      have bench data. A regression (negative improvement) rejects.
    """
    gates_passed: list[str] = []
    gates_failed: list[str] = []
    benchmark_cmp: Optional[BenchmarkComparison] = None

    # --- Gate 1: tests must pass ---
    test_step = _find_step(candidate_result, "test")
    if test_step is None or not test_step.is_success:
        reason = (
            "Tests failed" if test_step else "No test step ran"
        )
        gates_failed.append("test_gate")
        return AcceptanceVerdict(
            is_accepted=False,
            confidence=CONFIDENCE_LOW,
            reason=reason,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
        )
    gates_passed.append("test_gate")

    # --- Gate 2: typecheck (soft gate) ---
    typecheck_step = _find_step(candidate_result, "typecheck")
    typecheck_ok = typecheck_step is None or typecheck_step.is_success
    if not typecheck_ok:
        gates_failed.append("typecheck_gate")
        logger.warning("Typecheck failed for candidate; confidence downgraded to low")
    elif typecheck_step is not None:
        gates_passed.append("typecheck_gate")

    # --- Gate 3: benchmark (conditional) ---
    benchmark_cmp = compare_benchmarks(baseline_result, candidate_result)
    if benchmark_cmp is not None:
        if benchmark_cmp.improvement_pct < 0:
            # Regression — reject
            gates_failed.append("benchmark_gate")
            return AcceptanceVerdict(
                is_accepted=False,
                confidence=CONFIDENCE_LOW,
                reason=(
                    f"Benchmark regression: candidate is "
                    f"{abs(benchmark_cmp.improvement_pct):.1f}% slower than baseline"
                ),
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                benchmark_comparison=benchmark_cmp,
            )
        elif benchmark_cmp.passes_threshold:
            gates_passed.append("benchmark_gate")
        else:
            # Improvement exists but below 3% threshold — not a failure, just medium confidence
            logger.debug(
                "Benchmark improvement %.2f%% is below threshold; treating as no benchmark",
                benchmark_cmp.improvement_pct,
            )

    # --- Determine confidence ---
    confidence, reason = _determine_confidence(
        typecheck_ok=typecheck_ok,
        benchmark_cmp=benchmark_cmp,
    )

    return AcceptanceVerdict(
        is_accepted=True,
        confidence=confidence,
        reason=reason,
        gates_passed=gates_passed,
        gates_failed=gates_failed,
        benchmark_comparison=benchmark_cmp,
    )


def _determine_confidence(
    typecheck_ok: bool,
    benchmark_cmp: Optional[BenchmarkComparison],
) -> tuple[str, str]:
    """Return (confidence_level, reason) based on gate outcomes."""
    if not typecheck_ok:
        return (
            CONFIDENCE_LOW,
            "Tests pass but typecheck failed; PR created with manual review required",
        )

    if benchmark_cmp is not None and benchmark_cmp.passes_threshold:
        return (
            CONFIDENCE_HIGH,
            f"Tests pass and benchmark shows {benchmark_cmp.improvement_pct:.1f}% improvement",
        )

    return (
        CONFIDENCE_MEDIUM,
        "Tests pass; no benchmark available — classified as tech-debt-safe improvement",
    )


def _find_step(result: BaselineResult, name: str):
    """Find a step by name in a BaselineResult, returning None if absent."""
    return next((s for s in result.steps if s.name == name), None)
