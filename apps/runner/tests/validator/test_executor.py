"""Unit tests for the baseline execution pipeline.

Tests run_step() and run_baseline() with mocked subprocess calls.
No actual commands are executed.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from runner.sandbox.limits import apply_resource_limits

from runner.detector.types import DetectionResult
from runner.validator.executor import _install_step_env, _make_preexec_fn, _prepare_test_step, run_baseline, run_step
from runner.validator.types import PipelineError


class TestRunStep:
    @patch("runner.validator.executor.subprocess.run")
    def test_successful_step(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="All tests passed",
            stderr="",
        )
        result = run_step("test", "npm test", tmp_path)

        assert result.is_success is True
        assert result.name == "test"
        assert result.stdout == "All tests passed"
        assert result.exit_code == 0
        assert result.duration_seconds >= 0

    @patch("runner.validator.executor.subprocess.run")
    def test_failed_step(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: test failed",
        )
        result = run_step("test", "npm test", tmp_path)

        assert result.is_success is False
        assert result.exit_code == 1
        assert "test failed" in result.stderr

    @patch("runner.validator.executor.subprocess.run")
    def test_timeout_returns_negative_exit(self, mock_run, tmp_path):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="npm test", timeout=300)

        result = run_step("test", "npm test", tmp_path, timeout=300)

        assert result.exit_code == -1
        assert "Timed out" in result.stderr

    @patch("runner.validator.executor.subprocess.run")
    def test_unexpected_exception(self, mock_run, tmp_path):
        mock_run.side_effect = OSError("No such file or directory")

        result = run_step("install", "npm ci", tmp_path)

        assert result.exit_code == -2
        assert "No such file" in result.stderr

    @patch("runner.validator.executor.subprocess.run")
    def test_uses_shell_mode(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_step("build", "npm run build", tmp_path)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["shell"] is True

    @patch("runner.validator.executor.subprocess.run")
    def test_passes_cwd(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_step("build", "npm run build", tmp_path)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == str(tmp_path)

    @patch("runner.validator.executor.subprocess.run")
    def test_custom_timeout(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_step("build", "npm run build", tmp_path, timeout=60)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 60

    @patch("runner.validator.executor.subprocess.run")
    def test_sets_js_resource_profile_for_js_commands(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_step("build", "npm run build", tmp_path)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"]["CORELOOP_RESOURCE_PROFILE"] == "js"

    @patch("runner.validator.executor.subprocess.run")
    def test_sets_default_resource_profile_for_non_js_commands(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_step("test", "pytest -q", tmp_path)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"]["CORELOOP_RESOURCE_PROFILE"] == "default"

    @patch("runner.validator.executor.subprocess.run")
    def test_sets_jvm_resource_profile_for_gradle_commands(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_step("build", "./gradlew build", tmp_path)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"]["CORELOOP_RESOURCE_PROFILE"] == "jvm"

    @patch("runner.validator.executor.subprocess.run")
    def test_sets_native_resource_profile_for_rust_commands(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_step("build", "cargo build --release", tmp_path)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"]["CORELOOP_RESOURCE_PROFILE"] == "native"

    @patch("runner.validator.executor.subprocess.run")
    def test_sets_native_resource_profile_for_cpp_commands(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_step("build", "cmake --build build", tmp_path)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"]["CORELOOP_RESOURCE_PROFILE"] == "native"


class TestMakePreexecFn:
    """Verify that _make_preexec_fn propagates resource-limit env keys to os.environ."""

    @patch("runner.validator.executor.apply_resource_limits")
    def test_syncs_resource_profile_into_os_environ(self, mock_apply):
        """preexec_fn must set CORELOOP_RESOURCE_PROFILE in os.environ so
        apply_resource_limits (which reads os.environ) sees the correct profile."""
        subprocess_env = {
            "CORELOOP_RESOURCE_PROFILE": "js",
            "CORELOOP_RLIMIT_AS_BYTES_JS": "0",
            "PATH": "/usr/bin",
        }

        preexec = _make_preexec_fn(subprocess_env)
        preexec()

        assert os.environ.get("CORELOOP_RESOURCE_PROFILE") == "js"
        assert os.environ.get("CORELOOP_RLIMIT_AS_BYTES_JS") == "0"
        mock_apply.assert_called_once()

    @patch("runner.validator.executor.apply_resource_limits")
    def test_does_not_propagate_non_rlimit_keys(self, mock_apply):
        subprocess_env = {
            "CORELOOP_RESOURCE_PROFILE": "native",
            "PATH": "/custom/path",
            "NODE_ENV": "development",
        }

        old_path = os.environ.get("PATH")
        preexec = _make_preexec_fn(subprocess_env)
        preexec()

        assert os.environ.get("PATH") == old_path
        assert os.environ.get("CORELOOP_RESOURCE_PROFILE") == "native"

    @patch("runner.validator.executor.subprocess.run")
    def test_run_step_passes_preexec_with_env(self, mock_run, tmp_path):
        """run_step must pass a preexec_fn that carries the subprocess env, not the bare function."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_step("test", "npm test", tmp_path)

        call_kwargs = mock_run.call_args[1]
        preexec = call_kwargs["preexec_fn"]
        assert preexec is not apply_resource_limits
        assert callable(preexec)


class TestInstallStepEnv:
    @pytest.mark.parametrize("pm", ["npm", "pnpm", "yarn", "bun", "NPM"])
    def test_js_package_managers_force_dev_dependencies(self, pm):
        env = _install_step_env(pm)
        assert env is not None
        assert env["NODE_ENV"] == "development"
        assert env["NPM_CONFIG_PRODUCTION"] == "false"

    def test_bundler_env_includes_test_dev_groups(self):
        env = _install_step_env("bundler")
        assert env is not None
        assert env["BUNDLE_DEPLOYMENT"] == "false"
        assert env["BUNDLE_FROZEN"] == "false"
        assert env["BUNDLE_WITHOUT"] == ""

    @pytest.mark.parametrize("pm", [None, "", "pip", "poetry", "cargo"])
    def test_non_js_package_managers_have_no_env_override(self, pm):
        assert _install_step_env(pm) is None


class TestPrepareTestStep:
    def test_vitest_script_is_throttled_for_npm_run_test(self, tmp_path):
        package_json = tmp_path / "package.json"
        package_json.write_text(
            '{"scripts":{"test":"vitest run --coverage"}}',
            encoding="utf-8",
        )

        command, env = _prepare_test_step(
            repo_dir=tmp_path,
            package_manager="npm",
            test_command="npm run test",
        )

        assert command.startswith("npm run test --")
        assert "--maxWorkers=1" in command
        assert "--pool=forks" in command
        assert env is not None
        assert env["CI"] == "true"

    def test_direct_vitest_command_is_throttled(self, tmp_path):
        command, env = _prepare_test_step(
            repo_dir=tmp_path,
            package_manager="pnpm",
            test_command="vitest run",
        )

        assert command == "vitest run --maxWorkers=1 --pool=forks"
        assert env is not None
        assert env["CI"] == "true"

    def test_non_vitest_js_test_stays_unchanged(self, tmp_path):
        package_json = tmp_path / "package.json"
        package_json.write_text(
            '{"scripts":{"test":"jest"}}',
            encoding="utf-8",
        )

        command, env = _prepare_test_step(
            repo_dir=tmp_path,
            package_manager="yarn",
            test_command="yarn test",
        )

        assert command == "yarn test"
        assert env is not None
        assert env["CI"] == "true"

    def test_non_js_test_has_no_overrides(self, tmp_path):
        command, env = _prepare_test_step(
            repo_dir=tmp_path,
            package_manager="pip",
            test_command="pytest -q",
        )

        assert command == "pytest -q"
        assert env is None


class TestRunBaseline:
    """Test the full baseline pipeline with mocked subprocess."""

    def _make_config(self, **overrides) -> DetectionResult:
        defaults = {
            "package_manager": "npm",
            "install_cmd": "npm ci",
            "build_cmd": "npm run build",
            "test_cmd": "npm test",
            "typecheck_cmd": None,
        }
        defaults.update(overrides)
        return DetectionResult(**defaults)

    @patch("runner.validator.executor.run_step")
    def test_happy_path_install_build_test(self, mock_step, tmp_path):
        """Full pipeline: install -> build -> test, all pass."""
        mock_step.side_effect = [
            MagicMock(is_success=True, name="install", duration_seconds=5.0),
            MagicMock(is_success=True, name="build", duration_seconds=10.0),
            MagicMock(is_success=True, name="test", duration_seconds=8.0),
        ]
        config = self._make_config()

        result = run_baseline(tmp_path, config)

        assert result.is_success is True
        assert len(result.steps) == 3
        assert result.error is None

    @patch("runner.validator.executor.run_step")
    def test_install_step_uses_dev_env_for_npm(self, mock_step, tmp_path):
        """Install step forces devDependencies for JS package managers."""
        mock_step.side_effect = [
            MagicMock(is_success=True, name="install", duration_seconds=5.0),
            MagicMock(is_success=True, name="build", duration_seconds=10.0),
            MagicMock(is_success=True, name="test", duration_seconds=8.0),
        ]
        config = self._make_config(package_manager="npm")

        run_baseline(tmp_path, config)

        install_call = mock_step.call_args_list[0]
        assert install_call.args[0] == "install"
        assert install_call.kwargs["env"]["NODE_ENV"] == "development"
        assert install_call.kwargs["env"]["NPM_CONFIG_PRODUCTION"] == "false"

    @patch("runner.validator.executor.run_step")
    def test_install_step_has_no_env_override_for_non_js_pm(self, mock_step, tmp_path):
        mock_step.side_effect = [
            MagicMock(is_success=True, name="install", duration_seconds=5.0),
            MagicMock(is_success=True, name="build", duration_seconds=10.0),
            MagicMock(is_success=True, name="test", duration_seconds=8.0),
        ]
        config = self._make_config(package_manager="pip", install_cmd="pip install -r requirements.txt")

        run_baseline(tmp_path, config)

        install_call = mock_step.call_args_list[0]
        assert install_call.args[0] == "install"
        assert install_call.kwargs["env"] is None

    @patch("runner.validator.executor.run_step")
    def test_install_step_uses_bundler_env(self, mock_step, tmp_path):
        mock_step.side_effect = [
            MagicMock(is_success=True, name="install", duration_seconds=5.0),
            MagicMock(is_success=True, name="build", duration_seconds=10.0),
            MagicMock(is_success=True, name="test", duration_seconds=8.0),
        ]
        config = self._make_config(
            package_manager="bundler",
            install_cmd="bundle install",
            build_cmd="bundle exec rake build",
            test_cmd="bundle exec rspec",
        )

        run_baseline(tmp_path, config)

        install_call = mock_step.call_args_list[0]
        assert install_call.args[0] == "install"
        assert install_call.kwargs["env"]["BUNDLE_DEPLOYMENT"] == "false"
        assert install_call.kwargs["env"]["BUNDLE_FROZEN"] == "false"
        assert install_call.kwargs["env"]["BUNDLE_WITHOUT"] == ""

    @patch("runner.validator.executor.run_step")
    def test_install_failure_aborts_pipeline(self, mock_step, tmp_path):
        """Install is critical; failure stops the entire pipeline."""
        mock_step.return_value = MagicMock(
            is_success=False, exit_code=1, name="install", duration_seconds=2.0,
            command="npm ci",
        )
        # Make it a proper StepResult-like object for PipelineError
        from runner.validator.types import StepResult
        mock_step.return_value = StepResult(
            name="install", command="npm ci", exit_code=1, duration_seconds=2.0,
            stderr="npm ERR! ERESOLVE",
        )
        config = self._make_config()

        result = run_baseline(tmp_path, config)

        assert result.is_success is False
        assert "install" in result.error.lower()
        assert len(result.steps) == 1  # Only install ran

    @patch("runner.validator.executor.run_step")
    def test_test_failure_aborts_pipeline(self, mock_step, tmp_path):
        """Test is critical; failure stops after test step."""
        from runner.validator.types import StepResult
        mock_step.side_effect = [
            StepResult(name="install", command="npm ci", exit_code=0, duration_seconds=5.0),
            StepResult(name="build", command="npm run build", exit_code=0, duration_seconds=10.0),
            StepResult(name="test", command="npm test", exit_code=1, duration_seconds=8.0,
                       stderr="FAIL src/app.test.ts"),
        ]
        config = self._make_config()

        result = run_baseline(tmp_path, config)

        assert result.is_success is False
        assert "test" in result.error.lower()
        assert len(result.steps) == 3

    @patch("runner.validator.executor.run_step")
    def test_build_failure_is_noncritical(self, mock_step, tmp_path):
        """Build failure doesn't stop the pipeline."""
        from runner.validator.types import StepResult
        mock_step.side_effect = [
            StepResult(name="install", command="npm ci", exit_code=0, duration_seconds=5.0),
            StepResult(name="build", command="npm run build", exit_code=1, duration_seconds=10.0),
            StepResult(name="test", command="npm test", exit_code=0, duration_seconds=8.0),
        ]
        config = self._make_config()

        result = run_baseline(tmp_path, config)

        assert result.is_success is True
        assert len(result.steps) == 3

    @patch("runner.validator.executor.run_step")
    def test_typecheck_included_when_configured(self, mock_step, tmp_path):
        from runner.validator.types import StepResult
        mock_step.side_effect = [
            StepResult(name="install", command="npm ci", exit_code=0, duration_seconds=5.0),
            StepResult(name="build", command="npm run build", exit_code=0, duration_seconds=10.0),
            StepResult(name="typecheck", command="npm run typecheck", exit_code=0, duration_seconds=3.0),
            StepResult(name="test", command="npm test", exit_code=0, duration_seconds=8.0),
        ]
        config = self._make_config(typecheck_cmd="npm run typecheck")

        result = run_baseline(tmp_path, config)

        assert result.is_success is True
        assert len(result.steps) == 4
        step_names = [s.name for s in result.steps]
        assert "typecheck" in step_names

    @patch("runner.validator.executor.run_step")
    def test_typecheck_failure_is_noncritical(self, mock_step, tmp_path):
        from runner.validator.types import StepResult
        mock_step.side_effect = [
            StepResult(name="install", command="npm ci", exit_code=0, duration_seconds=5.0),
            StepResult(name="build", command="npm run build", exit_code=0, duration_seconds=10.0),
            StepResult(name="typecheck", command="npm run typecheck", exit_code=2, duration_seconds=3.0),
            StepResult(name="test", command="npm test", exit_code=0, duration_seconds=8.0),
        ]
        config = self._make_config(typecheck_cmd="npm run typecheck")

        result = run_baseline(tmp_path, config)

        assert result.is_success is True

    @patch("runner.validator.executor.run_step")
    def test_no_build_cmd_skips_build(self, mock_step, tmp_path):
        from runner.validator.types import StepResult
        mock_step.side_effect = [
            StepResult(name="install", command="npm ci", exit_code=0, duration_seconds=5.0),
            StepResult(name="test", command="npm test", exit_code=0, duration_seconds=8.0),
        ]
        config = self._make_config(build_cmd=None)

        result = run_baseline(tmp_path, config)

        assert result.is_success is True
        assert len(result.steps) == 2
        step_names = [s.name for s in result.steps]
        assert "build" not in step_names

    @patch("runner.validator.executor.run_step")
    def test_bench_cmd_runs_when_provided(self, mock_step, tmp_path):
        from runner.validator.types import StepResult
        mock_step.side_effect = [
            StepResult(name="install", command="npm ci", exit_code=0, duration_seconds=5.0),
            StepResult(name="test", command="npm test", exit_code=0, duration_seconds=8.0),
            StepResult(name="bench", command="npm run bench", exit_code=0,
                       duration_seconds=15.0, stdout="Benchmark results"),
        ]
        config = self._make_config(build_cmd=None)

        result = run_baseline(tmp_path, config, bench_cmd="npm run bench")

        assert result.is_success is True
        assert result.bench_result is not None
        assert result.bench_result["command"] == "npm run bench"

    @patch("runner.validator.executor.run_step")
    def test_bench_failure_is_noncritical(self, mock_step, tmp_path):
        from runner.validator.types import StepResult
        mock_step.side_effect = [
            StepResult(name="install", command="npm ci", exit_code=0, duration_seconds=5.0),
            StepResult(name="test", command="npm test", exit_code=0, duration_seconds=8.0),
            StepResult(name="bench", command="npm run bench", exit_code=1, duration_seconds=5.0),
        ]
        config = self._make_config(build_cmd=None)

        result = run_baseline(tmp_path, config, bench_cmd="npm run bench")

        assert result.is_success is True
        assert result.bench_result is None

    @patch("runner.validator.executor.run_step")
    def test_no_test_cmd_skips_test(self, mock_step, tmp_path):
        from runner.validator.types import StepResult
        mock_step.side_effect = [
            StepResult(name="install", command="npm ci", exit_code=0, duration_seconds=5.0),
            StepResult(name="build", command="npm run build", exit_code=0, duration_seconds=10.0),
        ]
        config = self._make_config(test_cmd=None)

        result = run_baseline(tmp_path, config)

        assert result.is_success is True
        step_names = [s.name for s in result.steps]
        assert "test" not in step_names
