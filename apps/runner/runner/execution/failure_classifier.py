"""Failure signature classifier for adaptive execution fallbacks."""

from runner.execution.strategy_types import FailureReasonCode, StepFailure
from runner.validator.types import BaselineResult, StepResult


def classify_pipeline_failure(result: BaselineResult) -> StepFailure:
    """Classify the first failed step from a baseline result."""
    failed = next((step for step in result.steps if step.exit_code != 0), None)
    if not failed:
        return StepFailure(
            step_name="unknown",
            reason_code=FailureReasonCode.UNKNOWN,
        )

    reason = _classify_step_failure(failed)
    return StepFailure(
        step_name=failed.name,
        reason_code=reason,
        stdout=failed.stdout,
        stderr=failed.stderr,
    )


def _classify_step_failure(step: StepResult) -> FailureReasonCode:
    text = f"{step.stdout}\n{step.stderr}".lower()

    if _contains_any(
        text,
        (
            "out of memory",
            "heap out of memory",
            "wasm",
            "webassembly.instantiate()",
        ),
    ):
        if step.name == "test":
            return FailureReasonCode.CONCURRENCY_OOM
        return FailureReasonCode.OOM

    if _contains_any(
        text,
        (
            "lockfile would have been modified",
            "frozen-lockfile",
            "cannot install with \"frozen-lockfile\"",
            "package-lock.json and package.json are out of sync",
            "your lockfile needs to be updated",
            "pnpm-lock.yaml is absent",
            "npm err! code eusage",
        ),
    ):
        return FailureReasonCode.LOCKFILE_DRIFT

    if _contains_any(
        text,
        (
            "cannot find module 'vitest'",
            "cannot find module \"vitest\"",
            "cannot find module 'typescript'",
            "command not found: vitest",
            "vitest: not found",
            "tsc: not found",
            "jest: not found",
        ),
    ):
        return FailureReasonCode.MISSING_DEV_DEPENDENCIES

    if _contains_any(
        text,
        (
            "command not found",
            "is not recognized as an internal or external command",
            "no such file or directory",
            "executable file not found",
        ),
    ):
        if _contains_any(text, ("./gradlew", "./mvnw", "gradlew", "mvnw")):
            return FailureReasonCode.WRAPPER_MISSING
        return FailureReasonCode.COMMAND_NOT_FOUND

    if _contains_any(
        text,
        (
            "unsupported engine",
            "the engine \"node\" is incompatible",
            "requires node",
            "node version",
        ),
    ):
        return FailureReasonCode.ENGINE_MISMATCH

    if step.name == "install":
        return FailureReasonCode.INSTALL_FAILED
    if step.name == "test":
        return FailureReasonCode.TEST_FAILED
    if step.name == "build":
        return FailureReasonCode.BUILD_FAILED
    if step.name == "typecheck":
        return FailureReasonCode.TYPECHECK_FAILED
    return FailureReasonCode.UNKNOWN


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)
