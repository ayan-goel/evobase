"""Types for the baseline and candidate execution pipelines.

StepResult and BaselineResult capture baseline runs.
BenchmarkComparison, AcceptanceVerdict, AttemptRecord, and CandidateResult
capture the candidate validation pass.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class StepResult:
    """Result of a single pipeline step (install, build, test, etc.).

    Captures exit code, timing, and output for evidence.
    A step is successful if exit_code == 0.
    """

    name: str
    command: str
    exit_code: int
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "command": self.command,
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration_seconds, 3),
            "stdout_lines": self.stdout.count("\n") + 1 if self.stdout else 0,
            "stderr_lines": self.stderr.count("\n") + 1 if self.stderr else 0,
            "is_success": self.is_success,
        }


@dataclass
class BaselineResult:
    """Complete baseline pipeline result.

    Aggregates all step results and determines overall success.
    A baseline is successful only if all executed steps pass.
    """

    steps: list[StepResult] = field(default_factory=list)
    bench_result: Optional[dict] = None
    is_success: bool = False
    error: Optional[str] = None
    # Strategy metadata for strict/adaptive execution attempts.
    strategy_attempts: int = 1
    strategy_mode: str = "strict"
    failure_reason_code: Optional[str] = None
    adaptive_transition_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "bench_result": self.bench_result,
            "is_success": self.is_success,
            "error": self.error,
            "strategy_attempts": self.strategy_attempts,
            "strategy_mode": self.strategy_mode,
            "failure_reason_code": self.failure_reason_code,
            "adaptive_transition_reason": self.adaptive_transition_reason,
            "total_duration_seconds": round(
                sum(s.duration_seconds for s in self.steps), 3
            ),
        }


class PipelineError(Exception):
    """Raised when a critical pipeline step fails.

    Carries the step result for detailed error reporting.
    Non-critical steps (typecheck, bench) do not raise this.
    """

    def __init__(self, step_result: StepResult, message: str = ""):
        self.step_result = step_result
        super().__init__(
            message or f"Step '{step_result.name}' failed with exit code {step_result.exit_code}"
        )


# ---------------------------------------------------------------------------
# Candidate validation types
# ---------------------------------------------------------------------------

# Noise floor for benchmark significance: improvements below this are considered noise
BENCHMARK_NOISE_THRESHOLD_PCT = 1.0

# Minimum improvement percentage to accept a benchmark-gated patch
BENCHMARK_MIN_IMPROVEMENT_PCT = 3.0


@dataclass
class BenchmarkComparison:
    """Comparison between baseline and candidate benchmark results.

    improvement_pct: positive = candidate is faster, negative = regression.
    is_significant: True if improvement exceeds the noise floor.
    passes_threshold: True if improvement meets the ≥3% acceptance bar.
    """

    baseline_duration_seconds: float
    candidate_duration_seconds: float
    improvement_pct: float
    is_significant: bool
    passes_threshold: bool

    def to_dict(self) -> dict:
        return {
            "baseline_duration_seconds": round(self.baseline_duration_seconds, 3),
            "candidate_duration_seconds": round(self.candidate_duration_seconds, 3),
            "improvement_pct": round(self.improvement_pct, 2),
            "is_significant": self.is_significant,
            "passes_threshold": self.passes_threshold,
        }


# Confidence levels from highest to lowest assurance
CONFIDENCE_HIGH = "high"       # tests pass + benchmark shows ≥3% improvement
CONFIDENCE_MEDIUM = "medium"   # tests pass + no benchmark (tech debt safe)
CONFIDENCE_LOW = "low"         # tests pass + typecheck failed (labeled, PR disabled)


@dataclass
class AcceptanceVerdict:
    """Final accept/reject decision for a candidate patch.

    is_accepted: whether the patch meets all required gates.
    confidence: "high", "medium", or "low" — controls PR creation gating.
    reason: human-readable summary of why the verdict was reached.
    gates_passed / gates_failed: list of gate names for traceability.
    benchmark_comparison: populated when benchmark data was available.
    """

    is_accepted: bool
    confidence: str
    reason: str
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)
    benchmark_comparison: Optional[BenchmarkComparison] = None

    def to_dict(self) -> dict:
        return {
            "is_accepted": self.is_accepted,
            "confidence": self.confidence,
            "reason": self.reason,
            "gates_passed": self.gates_passed,
            "gates_failed": self.gates_failed,
            "benchmark_comparison": (
                self.benchmark_comparison.to_dict()
                if self.benchmark_comparison
                else None
            ),
        }


@dataclass
class AttemptRecord:
    """Full record of one validation attempt.

    Captures whether the patch applied, pipeline outcome, and verdict.
    Multiple attempts exist when the first test run triggers a flaky rerun.
    """

    attempt_number: int
    patch_applied: bool
    pipeline_result: Optional[BaselineResult]
    verdict: Optional[AcceptanceVerdict]
    error: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "attempt_number": self.attempt_number,
            "patch_applied": self.patch_applied,
            "pipeline_result": self.pipeline_result.to_dict() if self.pipeline_result else None,
            "verdict": self.verdict.to_dict() if self.verdict else None,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class CandidateResult:
    """Aggregated result of all validation attempts for a single patch.

    attempts: ordered list of all attempts (1 normally, 2 on flaky rerun).
    final_verdict: the verdict from the last decisive attempt.
    is_accepted: True only if the patch passed all gates.
    """

    attempts: list[AttemptRecord] = field(default_factory=list)
    final_verdict: Optional[AcceptanceVerdict] = None
    is_accepted: bool = False

    def to_dict(self) -> dict:
        return {
            "attempts": [a.to_dict() for a in self.attempts],
            "final_verdict": self.final_verdict.to_dict() if self.final_verdict else None,
            "is_accepted": self.is_accepted,
        }
