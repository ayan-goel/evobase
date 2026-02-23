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


def test_node_retries_when_build_fails_before_test_with_oom(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"test":"vitest run --coverage"}}',
        encoding="utf-8",
    )
    detection = DetectionResult(
        language="javascript",
        package_manager="npm",
        install_cmd="npm ci",
        build_cmd="npm run build",
        test_cmd="npm run test",
    )
    calls: list[tuple[str, str]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command))
        test_calls = [call for call in calls if call[0] == "test"]
        if name == "build":
            return StepResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.02,
                stderr="RangeError: WebAssembly.instantiate(): Out of memory",
            )
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
    assert len(test_commands) == 2
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


def test_jvm_strict_plan_sets_bounded_runtime_env_flags(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="java",
        package_manager="gradle",
        install_cmd="./gradlew dependencies",
        build_cmd="./gradlew build",
        test_cmd="./gradlew test",
    )
    calls: list[tuple[str, str, dict | None]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command, env))
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(mode=ExecutionMode.STRICT, max_attempts=2),
    )

    assert result.is_success is True
    assert result.strategy_attempts == 1
    assert len(calls) == 3

    install_env = calls[0][2]
    build_env = calls[1][2]
    test_env = calls[2][2]
    assert install_env is not None
    assert build_env is not None
    assert test_env is not None
    assert "Xmx4096m" in install_env.get("JAVA_TOOL_OPTIONS", "")
    assert "Xmx4096m" in test_env.get("MAVEN_OPTS", "")
    assert "org.gradle.workers.max=2" in build_env.get("GRADLE_OPTS", "")


def test_jvm_oom_retries_with_tighter_heap_and_worker_flags(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="java",
        package_manager="gradle",
        install_cmd="./gradlew dependencies",
        test_cmd="./gradlew test",
    )
    calls: list[tuple[str, str, dict | None]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command, env))
        test_calls = [call for call in calls if call[0] == "test"]
        if name == "test" and len(test_calls) == 1:
            return StepResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.01,
                stderr="java.lang.OutOfMemoryError: Java heap space",
            )
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(mode=ExecutionMode.ADAPTIVE, max_attempts=2),
    )

    test_envs = [env for name, _, env in calls if name == "test"]
    assert len(test_envs) == 2
    assert test_envs[0] is not None
    assert test_envs[1] is not None
    assert "Xmx4096m" in test_envs[0].get("JAVA_TOOL_OPTIONS", "")
    assert "Xmx3072m" in test_envs[1].get("JAVA_TOOL_OPTIONS", "")
    assert "org.gradle.workers.max=1" in test_envs[1].get("GRADLE_OPTS", "")
    assert result.is_success is True
    assert result.strategy_attempts == 2


def test_rust_strict_plan_sets_bounded_cargo_env(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="rust",
        package_manager="cargo",
        install_cmd="cargo fetch",
        build_cmd="cargo build",
        test_cmd="cargo test",
    )
    calls: list[tuple[str, str, dict | None]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command, env))
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(mode=ExecutionMode.STRICT, max_attempts=2),
    )

    assert result.is_success is True
    assert result.strategy_attempts == 1
    envs = [env for _, _, env in calls]
    assert all(env is not None for env in envs)
    assert envs[0].get("CARGO_BUILD_JOBS") == "2"
    assert envs[1].get("CARGO_BUILD_JOBS") == "2"
    assert envs[2].get("CARGO_INCREMENTAL") == "0"


def test_rust_linker_failure_retries_with_single_cargo_job(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="rust",
        package_manager="cargo",
        install_cmd="cargo fetch",
        test_cmd="cargo test",
    )
    calls: list[tuple[str, str, dict | None]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command, env))
        test_calls = [call for call in calls if call[0] == "test"]
        if name == "test" and len(test_calls) == 1:
            return StepResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.01,
                stderr="error: linking with `cc` failed: linker command failed: cannot allocate memory",
            )
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(mode=ExecutionMode.ADAPTIVE, max_attempts=2),
    )

    test_envs = [env for name, _, env in calls if name == "test"]
    assert len(test_envs) == 2
    assert test_envs[0] is not None
    assert test_envs[1] is not None
    assert test_envs[0].get("CARGO_BUILD_JOBS") == "2"
    assert test_envs[1].get("CARGO_BUILD_JOBS") == "1"
    assert result.is_success is True
    assert result.strategy_attempts == 2


def test_cpp_strict_plan_sets_bounded_parallelism_env(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="cpp",
        package_manager="cmake",
        install_cmd="cmake -S . -B build",
        build_cmd="cmake --build build",
        test_cmd="ctest --test-dir build",
    )
    calls: list[tuple[str, str, dict | None]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command, env))
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(mode=ExecutionMode.STRICT, max_attempts=2),
    )

    assert result.is_success is True
    assert result.strategy_attempts == 1
    install_env = calls[0][2]
    build_env = calls[1][2]
    test_env = calls[2][2]
    assert install_env is not None
    assert build_env is not None
    assert test_env is not None
    assert install_env.get("CMAKE_BUILD_PARALLEL_LEVEL") == "2"
    assert build_env.get("MAKEFLAGS") == "-j2"
    assert test_env.get("CMAKE_BUILD_PARALLEL_LEVEL") == "2"


def test_cpp_linker_oom_retries_with_single_parallel_worker(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="cpp",
        package_manager="cmake",
        install_cmd="cmake -S . -B build",
        test_cmd="ctest --test-dir build",
    )
    calls: list[tuple[str, str, dict | None]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command, env))
        test_calls = [call for call in calls if call[0] == "test"]
        if name == "test" and len(test_calls) == 1:
            return StepResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.01,
                stderr="collect2: fatal error: ld terminated with signal 9 [Killed]",
            )
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(mode=ExecutionMode.ADAPTIVE, max_attempts=2),
    )

    test_envs = [env for name, _, env in calls if name == "test"]
    assert len(test_envs) == 2
    assert test_envs[0] is not None
    assert test_envs[1] is not None
    assert test_envs[0].get("CMAKE_BUILD_PARALLEL_LEVEL") == "2"
    assert test_envs[1].get("CMAKE_BUILD_PARALLEL_LEVEL") == "1"
    assert result.is_success is True
    assert result.strategy_attempts == 2


def test_python_missing_dev_dependencies_retries_with_dev_install(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="python",
        package_manager="poetry",
        install_cmd="poetry install",
        test_cmd="pytest -q",
    )
    calls: list[tuple[str, str, dict | None]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command, env))
        test_calls = [call for call in calls if call[0] == "test"]
        if name == "test" and len(test_calls) == 1:
            return StepResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.01,
                stderr="ModuleNotFoundError: No module named 'pytest'",
            )
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(mode=ExecutionMode.ADAPTIVE, max_attempts=2),
    )

    install_commands = [command for name, command, _ in calls if name == "install"]
    assert install_commands == ["poetry install", "poetry install --with dev"]
    assert result.is_success is True
    assert result.strategy_attempts == 2


def test_ruby_install_oom_retries_with_single_bundler_job(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="ruby",
        package_manager="bundler",
        install_cmd="bundle install",
        test_cmd="bundle exec rspec",
    )
    calls: list[tuple[str, str, dict | None]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command, env))
        install_calls = [call for call in calls if call[0] == "install"]
        if name == "install" and len(install_calls) == 1:
            return StepResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.01,
                stderr="fatal: out of memory",
            )
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(mode=ExecutionMode.ADAPTIVE, max_attempts=2),
    )

    install_envs = [env for name, _, env in calls if name == "install"]
    assert len(install_envs) == 2
    assert install_envs[0] is not None
    assert install_envs[1] is not None
    assert install_envs[0].get("BUNDLE_JOBS") == "2"
    assert install_envs[1].get("BUNDLE_JOBS") == "1"
    assert result.is_success is True
    assert result.strategy_attempts == 2


def test_go_test_oom_retries_with_parallel_flags(tmp_path: Path) -> None:
    detection = DetectionResult(
        language="go",
        package_manager="go",
        install_cmd="go mod download",
        test_cmd="go test ./...",
    )
    calls: list[tuple[str, str, dict | None]] = []

    def fake_run_step(name, command, cwd, timeout=300, env=None):
        calls.append((name, command, env))
        test_calls = [call for call in calls if call[0] == "test"]
        if name == "test" and len(test_calls) == 1:
            return StepResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.01,
                stderr="runtime: out of memory",
            )
        return _ok_step(name, command)

    result = run_with_strategy(
        repo_dir=tmp_path,
        detection=detection,
        run_step=fake_run_step,
        strategy_settings=StrategySettings(mode=ExecutionMode.ADAPTIVE, max_attempts=2),
    )

    test_commands = [command for name, command, _ in calls if name == "test"]
    assert len(test_commands) == 2
    assert test_commands[0] == "go test ./..."
    assert "-parallel=1" in test_commands[1]
    assert "-p=1" in test_commands[1]
    assert result.is_success is True
    assert result.strategy_attempts == 2


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
