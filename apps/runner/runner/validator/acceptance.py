"""Acceptance logic for candidate patches.

Gates (in order of application):
  1. test_gate         — candidate tests must pass (always required)
  2. build_gate        — if a build_cmd ran, it must succeed (hard rejection;
                          a patch that breaks the build must never become a
                          proposal)
  3. source_safety_gate — if JS/TS source files were touched, some compile-
                          level tool (build OR typecheck) must have run. A
                          patch that produces syntactically broken output
                          would otherwise slip through when the repo has no
                          build step configured.
  4. typecheck_gate     — candidate typecheck must pass (if available;
                          failure downgrades confidence to "low" but does
                          not reject)
  5. benchmark_gate     — if baseline has bench data, candidate must show
                          ≥3% improvement beyond noise (rejects if it
                          regresses)

Confidence levels:
  high   — tests pass + benchmark shows ≥3% improvement
  medium — tests pass + no benchmark available (tech debt safe)
  low    — tests pass + typecheck failed (PR created but flagged disabled)
"""

import logging
from pathlib import PurePosixPath
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

# File extensions that require a compile-level check (build or typecheck)
# before the patch can be accepted. Source files in these languages can be
# syntactically broken in ways that runtime tests do not always catch.
_COMPILE_REQUIRED_EXTENSIONS = frozenset({
    ".js", ".jsx", ".mjs", ".cjs",
    ".ts", ".tsx", ".mts", ".cts",
})


def _requires_compile_check(touched_files: list[str]) -> bool:
    """Return True if any touched file has an extension that requires compile verification."""
    return any(
        PurePosixPath(path).suffix.lower() in _COMPILE_REQUIRED_EXTENSIONS
        for path in touched_files
    )


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
    touched_files: Optional[list[str]] = None,
) -> AcceptanceVerdict:
    """Apply all acceptance gates and return the final verdict.

    test_gate is hard: failure rejects immediately.
    build_gate is hard when it ran: a failing build rejects immediately.
    source_safety_gate is hard when ``touched_files`` contains JS/TS sources
      and neither build nor typecheck ran (no compile verification).
    typecheck_gate is soft: failure downgrades confidence.
    benchmark_gate is conditional: only applied when both runs have bench
      data. A regression (negative improvement) rejects.

    ``touched_files`` is optional for backward compatibility; when omitted
    the source_safety_gate is skipped and legacy callers continue to work.
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

    # --- Gate 2: build must pass (hard gate, only when build ran) ---
    # A patch that breaks the build is never safe to propose regardless of
    # passing tests — it would cause CI/CD failures on the target branch.
    build_step = _find_step(candidate_result, "build")
    if build_step is not None and not build_step.is_success:
        gates_failed.append("build_gate")
        return AcceptanceVerdict(
            is_accepted=False,
            confidence=CONFIDENCE_LOW,
            reason="Build failed — patch introduces a compilation or build error",
            gates_passed=gates_passed,
            gates_failed=gates_failed,
        )
    if build_step is not None:
        gates_passed.append("build_gate")

    # --- Source-safety gate: JS/TS patches need a compile-level check ---
    # Runtime tests can miss broken JSX/TS that would fail `next build` or
    # `tsc --noEmit`. If the candidate touches JS/TS files and neither a
    # build nor a typecheck actually ran, we have no evidence the patched
    # output even parses — reject to avoid shipping uncompilable code.
    typecheck_step = _find_step(candidate_result, "typecheck")
    if touched_files and _requires_compile_check(touched_files):
        if build_step is None and typecheck_step is None:
            gates_failed.append("source_safety_gate")
            logger.warning(
                "Rejecting candidate: touched %d JS/TS file(s) but no build "
                "or typecheck step verified they compile",
                sum(1 for f in touched_files if _requires_compile_check([f])),
            )
            return AcceptanceVerdict(
                is_accepted=False,
                confidence=CONFIDENCE_LOW,
                reason=(
                    "JS/TS files touched but no build or typecheck step "
                    "verified they compile — cannot accept without a "
                    "compile-level check"
                ),
                gates_passed=gates_passed,
                gates_failed=gates_failed,
            )
        gates_passed.append("source_safety_gate")

    # --- Gate 3: typecheck (soft gate) ---
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
