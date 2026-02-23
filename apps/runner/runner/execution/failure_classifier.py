"""Failure signature classifier for adaptive execution fallbacks."""

from runner.execution.strategy_types import FailureReasonCode, StepFailure
from runner.validator.types import BaselineResult, StepResult


def classify_pipeline_failure(result: BaselineResult) -> StepFailure:
    """Classify baseline failure, preferring critical failed gates.

    Baseline fails only on critical gates (install/test). Optional steps like
    build/typecheck can fail earlier in the sequence and should not mask the
    decisive test/install failure used for adaptive retry decisions.
    """
    failed_steps = [step for step in result.steps if step.exit_code != 0]
    if not failed_steps:
        return StepFailure(
            step_name="unknown",
            reason_code=FailureReasonCode.UNKNOWN,
        )

    critical_failed = next(
        (step for step in failed_steps if step.name in {"install", "test"}),
        None,
    )
    failed = critical_failed or failed_steps[0]

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
            "outofmemoryerror",
            "java heap space",
            "gc overhead limit exceeded",
            "metaspace",
            "linker command failed",
            "ld terminated with signal 9",
            "collect2: fatal error",
            "cannot allocate memory",
            "ld: final link failed",
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
            "modulenotfounderror: no module named 'pytest'",
            "modulenotfounderror: no module named 'mypy'",
            "importerror: cannot import name 'pytest'",
            "importerror: cannot import name \"pytest\"",
            "command not found: vitest",
            "vitest: not found",
            "tsc: not found",
            "jest: not found",
            "pytest: command not found",
            "mypy: command not found",
            "cannot load such file -- rspec",
            "uninitialized constant rspec",
            "rspec: command not found",
        ),
    ):
        return FailureReasonCode.MISSING_DEV_DEPENDENCIES

    if _contains_any(
        text,
        (
            "missing go.sum entry",
            "go.mod and go.sum are out of sync",
            "go: inconsistent vendoring",
            "no required module provides package",
            "go: module",
            "proxy.golang.org",
            "context deadline exceeded",
        ),
    ):
        return FailureReasonCode.INSTALL_FAILED

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
