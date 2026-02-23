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


def test_prefers_critical_test_failure_over_noncritical_build_failure() -> None:
    result = BaselineResult(
        steps=[
            StepResult(
                name="build",
                command="npm run build",
                exit_code=1,
                duration_seconds=0.01,
                stderr="RangeError: WebAssembly.instantiate(): Out of memory",
            ),
            StepResult(
                name="test",
                command="npm run test",
                exit_code=1,
                duration_seconds=0.01,
                stderr="RangeError: WebAssembly.instantiate(): Out of memory",
            ),
        ],
        is_success=False,
    )
    classified = classify_pipeline_failure(result)
    assert classified.step_name == "test"
    assert classified.reason_code.value == "concurrency_oom"


def test_classifies_jvm_java_heap_space_as_oom() -> None:
    result = BaselineResult(
        steps=[
            StepResult(
                name="build",
                command="./gradlew build",
                exit_code=1,
                duration_seconds=0.01,
                stderr="java.lang.OutOfMemoryError: Java heap space",
            )
        ],
        is_success=False,
    )
    classified = classify_pipeline_failure(result)
    assert classified.reason_code.value == "oom"


def test_classifies_jvm_gc_overhead_in_test_as_concurrency_oom() -> None:
    result = BaselineResult(
        steps=[
            StepResult(
                name="test",
                command="./gradlew test",
                exit_code=1,
                duration_seconds=0.01,
                stderr="java.lang.OutOfMemoryError: GC overhead limit exceeded",
            )
        ],
        is_success=False,
    )
    classified = classify_pipeline_failure(result)
    assert classified.reason_code.value == "concurrency_oom"


def test_classifies_rust_linker_out_of_memory_as_oom() -> None:
    result = BaselineResult(
        steps=[
            StepResult(
                name="build",
                command="cargo build --release",
                exit_code=1,
                duration_seconds=0.01,
                stderr="error: linking with `cc` failed: linker command failed: cannot allocate memory",
            )
        ],
        is_success=False,
    )
    classified = classify_pipeline_failure(result)
    assert classified.reason_code.value == "oom"


def test_classifies_cpp_linker_signal_killed_in_test_as_concurrency_oom() -> None:
    result = BaselineResult(
        steps=[
            StepResult(
                name="test",
                command="ctest --test-dir build",
                exit_code=1,
                duration_seconds=0.01,
                stderr="collect2: fatal error: ld terminated with signal 9 [Killed]",
            )
        ],
        is_success=False,
    )
    classified = classify_pipeline_failure(result)
    assert classified.reason_code.value == "concurrency_oom"


def test_classifies_python_missing_pytest_module_as_missing_dev_dependencies() -> None:
    result = BaselineResult(
        steps=[
            StepResult(
                name="test",
                command="pytest -q",
                exit_code=1,
                duration_seconds=0.01,
                stderr="ModuleNotFoundError: No module named 'pytest'",
            )
        ],
        is_success=False,
    )
    classified = classify_pipeline_failure(result)
    assert classified.reason_code.value == "missing_dev_dependencies"


def test_classifies_ruby_missing_rspec_as_missing_dev_dependencies() -> None:
    result = BaselineResult(
        steps=[
            StepResult(
                name="test",
                command="bundle exec rspec",
                exit_code=1,
                duration_seconds=0.01,
                stderr="cannot load such file -- rspec",
            )
        ],
        is_success=False,
    )
    classified = classify_pipeline_failure(result)
    assert classified.reason_code.value == "missing_dev_dependencies"


def test_classifies_go_missing_go_sum_entry_as_install_failed() -> None:
    result = BaselineResult(
        steps=[
            StepResult(
                name="test",
                command="go test ./...",
                exit_code=1,
                duration_seconds=0.01,
                stderr="missing go.sum entry for module providing package",
            )
        ],
        is_success=False,
    )
    classified = classify_pipeline_failure(result)
    assert classified.reason_code.value == "install_failed"
