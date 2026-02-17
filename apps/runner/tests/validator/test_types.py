"""Unit tests for baseline pipeline types."""

import pytest

from runner.validator.types import BaselineResult, PipelineError, StepResult


class TestStepResult:
    def test_success_when_exit_zero(self):
        step = StepResult(name="test", command="npm test", exit_code=0, duration_seconds=1.5)
        assert step.is_success is True

    def test_failure_when_nonzero_exit(self):
        step = StepResult(name="test", command="npm test", exit_code=1, duration_seconds=1.5)
        assert step.is_success is False

    def test_failure_on_timeout(self):
        step = StepResult(name="test", command="npm test", exit_code=-1, duration_seconds=300.0)
        assert step.is_success is False

    def test_to_dict_includes_all_fields(self):
        step = StepResult(
            name="build",
            command="npm run build",
            exit_code=0,
            duration_seconds=12.345,
            stdout="Build complete\nDone",
            stderr="",
        )
        d = step.to_dict()
        assert d["name"] == "build"
        assert d["command"] == "npm run build"
        assert d["exit_code"] == 0
        assert d["duration_seconds"] == 12.345
        assert d["stdout_lines"] == 2
        assert d["stderr_lines"] == 0
        assert d["is_success"] is True

    def test_to_dict_empty_stdout(self):
        step = StepResult(name="test", command="cmd", exit_code=0, duration_seconds=0.0)
        assert step.to_dict()["stdout_lines"] == 0

    def test_to_dict_rounds_duration(self):
        step = StepResult(name="test", command="cmd", exit_code=0, duration_seconds=1.23456789)
        assert step.to_dict()["duration_seconds"] == 1.235


class TestBaselineResult:
    def test_empty_result_is_not_success(self):
        result = BaselineResult()
        assert result.is_success is False

    def test_to_dict_includes_total_duration(self):
        result = BaselineResult(
            steps=[
                StepResult(name="install", command="npm ci", exit_code=0, duration_seconds=5.0),
                StepResult(name="test", command="npm test", exit_code=0, duration_seconds=10.0),
            ],
            is_success=True,
        )
        d = result.to_dict()
        assert d["total_duration_seconds"] == 15.0
        assert d["is_success"] is True
        assert len(d["steps"]) == 2

    def test_to_dict_with_error(self):
        result = BaselineResult(error="Install failed", is_success=False)
        d = result.to_dict()
        assert d["error"] == "Install failed"
        assert d["is_success"] is False

    def test_to_dict_with_bench_result(self):
        result = BaselineResult(
            is_success=True,
            bench_result={"command": "npm run bench", "stdout": "fast"},
        )
        d = result.to_dict()
        assert d["bench_result"]["command"] == "npm run bench"

    def test_to_dict_empty_steps(self):
        result = BaselineResult()
        d = result.to_dict()
        assert d["total_duration_seconds"] == 0.0
        assert d["steps"] == []


class TestPipelineError:
    def test_carries_step_result(self):
        step = StepResult(name="install", command="npm ci", exit_code=1, duration_seconds=2.0)
        err = PipelineError(step)
        assert err.step_result is step
        assert "install" in str(err)
        assert "exit code 1" in str(err)

    def test_custom_message(self):
        step = StepResult(name="test", command="npm test", exit_code=2, duration_seconds=1.0)
        err = PipelineError(step, "Tests are broken")
        assert str(err) == "Tests are broken"
        assert err.step_result.exit_code == 2
