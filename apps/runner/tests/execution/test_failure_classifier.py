"""Tests for baseline failure signature classification."""

from runner.execution.failure_classifier import classify_pipeline_failure
from runner.validator.types import BaselineResult, StepResult


def test_classifies_missing_dev_dependencies() -> None:
    result = BaselineResult(
        steps=[
            StepResult(name="install", command="npm ci", exit_code=0, duration_seconds=0.01),
            StepResult(
                name="test",
                command="npm run test",
                exit_code=1,
                duration_seconds=0.02,
                stderr="Error: Cannot find module 'vitest'",
            ),
        ],
        is_success=False,
    )
    classified = classify_pipeline_failure(result)
    assert classified.reason_code.value == "missing_dev_dependencies"


def test_classifies_wrapper_missing() -> None:
    result = BaselineResult(
        steps=[
            StepResult(
                name="install",
                command="./gradlew dependencies",
                exit_code=1,
                duration_seconds=0.01,
                stderr="./gradlew: No such file or directory",
            )
        ],
        is_success=False,
    )
    classified = classify_pipeline_failure(result)
    assert classified.reason_code.value == "wrapper_missing"
