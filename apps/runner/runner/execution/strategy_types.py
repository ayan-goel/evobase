"""Types for strict-then-adaptive baseline execution."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Optional, Protocol

from runner.detector.types import DetectionResult


class FailureReasonCode(StrEnum):
    """Normalized failure reasons used for adaptive fallback decisions."""

    UNKNOWN = "unknown"
    LOCKFILE_DRIFT = "lockfile_drift"
    MISSING_DEV_DEPENDENCIES = "missing_dev_dependencies"
    OOM = "oom"
    CONCURRENCY_OOM = "concurrency_oom"
    COMMAND_NOT_FOUND = "command_not_found"
    WRAPPER_MISSING = "wrapper_missing"
    ENGINE_MISMATCH = "engine_mismatch"
    INSTALL_FAILED = "install_failed"
    TEST_FAILED = "test_failed"
    BUILD_FAILED = "build_failed"
    TYPECHECK_FAILED = "typecheck_failed"


class AttemptMode(StrEnum):
    """Execution mode for a single attempt."""

    STRICT = "strict"
    ADAPTIVE = "adaptive"


class ExecutionMode(StrEnum):
    """Repository-level strategy mode."""

    STRICT = "strict"
    ADAPTIVE = "adaptive"


@dataclass
class StrategySettings:
    """Per-run strategy settings resolved from repository settings."""

    mode: ExecutionMode = ExecutionMode.ADAPTIVE
    max_attempts: int = 2

    @classmethod
    def from_values(
        cls,
        execution_mode: Optional[str] = None,
        max_strategy_attempts: Optional[int] = None,
    ) -> "StrategySettings":
        mode_raw = (execution_mode or ExecutionMode.ADAPTIVE.value).strip().lower()
        mode = (
            ExecutionMode.STRICT
            if mode_raw == ExecutionMode.STRICT.value
            else ExecutionMode.ADAPTIVE
        )
        attempts_raw = max_strategy_attempts if max_strategy_attempts is not None else 2
        # Hard safety cap: bounded adaptive retries only.
        attempts = max(1, min(3, int(attempts_raw)))
        return cls(mode=mode, max_attempts=attempts)


@dataclass
class ExecutionAttemptPlan:
    """Concrete command/env plan for one baseline attempt."""

    attempt_number: int
    mode: AttemptMode
    install_command: str
    build_command: Optional[str]
    typecheck_command: Optional[str]
    test_command: Optional[str]
    bench_command: Optional[str]
    shared_env: Optional[dict] = None
    install_env: Optional[dict] = None
    build_env: Optional[dict] = None
    test_env: Optional[dict] = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class StepFailure:
    """Information about a failed step from the previous attempt."""

    step_name: str
    reason_code: FailureReasonCode
    stdout: str = ""
    stderr: str = ""


@dataclass
class ExecutionContext:
    """Inputs required to build strategy attempts."""

    repo_dir: Path
    detection: DetectionResult
    bench_command: Optional[str]
    settings: StrategySettings


class EcosystemAdapter(Protocol):
    """Adapter contract for ecosystem-specific strategy behavior."""

    def build_strict_plan(self, context: ExecutionContext) -> ExecutionAttemptPlan:
        """Return the first deterministic attempt plan."""

    def build_adaptive_plan(
        self,
        context: ExecutionContext,
        previous_plan: ExecutionAttemptPlan,
        failure: StepFailure,
    ) -> Optional[ExecutionAttemptPlan]:
        """Return an adaptive retry plan, or None to stop retrying."""
