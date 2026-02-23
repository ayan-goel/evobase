"""Tests for strict-then-adaptive baseline strategy engine."""

from pathlib import Path

from runner.detector.types import DetectionResult
from runner.execution.strategy_engine import run_with_strategy
from runner.execution.strategy_types import ExecutionMode, StrategySettings
from runner.validator.types import StepResult


def _ok_step(name: str, command: str) -> StepResult:
    return StepResult(name=name, command=command, exit_code=0, duration_seconds=0.01)


def test_node_install_lockfile_drift_retries_with_relaxed_install(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="javascript",
        package_manager="npm",
        install_cmd="npm ci",
        test_cmd="npm test",
    )
    calls: list[tuple[str, str]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command))
        install_calls = [call for call in calls if call[0] == "install"]
        if name == "install" and len(install_calls) == 1:
            return StepResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.01,
                stderr="npm ERR! package-lock.json and package.json are out of sync",
            )
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(
            mode=ExecutionMode.ADAPTIVE,
            max_attempts=2,
        ),
    )

    install_commands = [command for name, command in calls if name == "install"]
    assert install_commands == ["npm ci", "npm install"]
    assert result.is_success is True
    assert result.strategy_attempts == 2
    assert result.strategy_mode == "adaptive"


def test_node_test_oom_retries_with_vitest_throttle(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"test":"vitest run --coverage"}}',
        encoding="utf-8",
    )
    detection = DetectionResult(
        language="javascript",
        package_manager="npm",
        install_cmd="npm ci",
        test_cmd="npm run test",
    )
    calls: list[tuple[str, str]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command))
        test_calls = [call for call in calls if call[0] == "test"]
        if name == "test" and len(test_calls) == 1:
            return StepResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.02,
                stderr="RangeError: WebAssembly.instantiate(): Out of memory",
            )
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(
            mode=ExecutionMode.ADAPTIVE,
            max_attempts=2,
        ),
    )

    test_commands = [command for name, command in calls if name == "test"]
    assert test_commands[0] == "npm run test"
    assert "--maxWorkers=1" in test_commands[1]
    assert "--pool=forks" in test_commands[1]
    assert result.is_success is True
    assert result.strategy_attempts == 2


def test_jvm_wrapper_missing_retries_with_system_gradle(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="java",
        package_manager="gradle",
        install_cmd="./gradlew dependencies",
        test_cmd="./gradlew test",
    )
    calls: list[tuple[str, str]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command))
        install_calls = [call for call in calls if call[0] == "install"]
        if name == "install" and len(install_calls) == 1:
            return StepResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.01,
                stderr="./gradlew: No such file or directory",
            )
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(mode=ExecutionMode.ADAPTIVE, max_attempts=2),
    )

    install_commands = [command for name, command in calls if name == "install"]
    test_commands = [command for name, command in calls if name == "test"]
    assert install_commands == ["./gradlew dependencies", "gradle dependencies"]
    assert test_commands[-1] == "gradle test"
    assert result.is_success is True


def test_strict_mode_does_not_retry_on_known_failure(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="javascript",
        package_manager="npm",
        install_cmd="npm ci",
        test_cmd="npm test",
    )
    install_calls = 0

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        nonlocal install_calls
        if name == "install":
            install_calls += 1
            return StepResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.01,
                stderr="npm ERR! package-lock.json and package.json are out of sync",
            )
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(mode=ExecutionMode.STRICT, max_attempts=2),
    )

    assert install_calls == 1
    assert result.is_success is False
    assert result.failure_reason_code == "lockfile_drift"
