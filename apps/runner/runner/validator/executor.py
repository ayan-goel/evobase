"""Baseline execution pipeline.

Runs install -> build -> typecheck -> test -> bench in sequence.
Critical steps (install, test) fail the entire pipeline.
Optional steps (build, typecheck, bench) are logged but don't block.

Each step runs as a subprocess with timeout enforcement and full
stdout/stderr capture for artifact storage.
"""

import logging
import os
import json
import subprocess
import time
from pathlib import Path
from typing import Optional

from runner.detector.types import DetectionResult
from runner.execution.strategy_engine import run_with_strategy
from runner.execution.strategy_types import StrategySettings
from runner.sandbox.limits import apply_resource_limits
from runner.validator.types import BaselineResult, PipelineError, StepResult

logger = logging.getLogger(__name__)

# Steps that abort the pipeline on failure
CRITICAL_STEPS = {"install", "test"}

# Default timeout per step (seconds)
DEFAULT_TIMEOUT = 300

# JS package managers that need devDependencies during baseline validation.
JS_PACKAGE_MANAGERS = {"npm", "pnpm", "yarn", "bun"}
RUBY_PACKAGE_MANAGERS = {"bundler"}


def _install_step_env(package_manager: Optional[str]) -> Optional[dict]:
    """Return env overrides for install step.

    Railway/production environments commonly set language-specific dependency
    filtering env vars. We normalize install-time env so baseline validation
    has the dependencies needed to run build/test commands.
    """
    pm = (package_manager or "").lower()
    if pm not in JS_PACKAGE_MANAGERS and pm not in RUBY_PACKAGE_MANAGERS:
        return None

    env = dict(os.environ)
    if pm in JS_PACKAGE_MANAGERS:
        env["NODE_ENV"] = "development"
        # npm/yarn honor this flag and install devDependencies even when process
        # env defaults to production.
        env["NPM_CONFIG_PRODUCTION"] = "false"

    if pm in RUBY_PACKAGE_MANAGERS:
        # Bundler deploy mode (or BUNDLE_WITHOUT) can exclude test/development
        # groups, making baseline test runs fail despite healthy repos.
        env["BUNDLE_DEPLOYMENT"] = "false"
        env["BUNDLE_FROZEN"] = "false"
        env["BUNDLE_WITHOUT"] = ""
    return env


def _prepare_test_step(
    repo_dir: Path,
    package_manager: Optional[str],
    test_command: str,
) -> tuple[str, Optional[dict]]:
    """Return command/env overrides for the baseline test step.

    For JS package managers we force CI mode and optionally throttle Vitest
    worker fan-out to reduce worker-memory spikes in constrained runtimes.
    """
    pm = (package_manager or "").lower()
    if pm not in JS_PACKAGE_MANAGERS:
        return test_command, None

    env = dict(os.environ)
    env["CI"] = "true"

    command = test_command
    if _is_vitest_command(repo_dir, test_command):
        command = _append_vitest_throttle_flags(test_command)

    return command, env


def _is_vitest_command(repo_dir: Path, test_command: str) -> bool:
    """Detect whether a test command resolves to Vitest."""
    lowered = test_command.lower()
    if "vitest" in lowered:
        return True
    if not _is_js_test_script_command(test_command):
        return False

    script = _read_package_json_test_script(repo_dir)
    return bool(script and "vitest" in script.lower())


def _is_js_test_script_command(command: str) -> bool:
    """Return True when the command is a package-manager test script invocation."""
    normalized = " ".join(command.strip().lower().split())
    return normalized.startswith(
        (
            "npm run test",
            "pnpm run test",
            "yarn test",
            "yarn run test",
            "bun test",
            "bun run test",
        )
    )


def _read_package_json_test_script(repo_dir: Path) -> Optional[str]:
    """Read scripts.test from package.json, if present."""
    package_json_path = repo_dir / "package.json"
    if not package_json_path.exists():
        return None
    try:
        payload = json.loads(package_json_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    scripts = payload.get("scripts", {})
    script = scripts.get("test")
    return script if isinstance(script, str) else None


def _append_vitest_throttle_flags(test_command: str) -> str:
    """Append conservative Vitest worker flags when not already specified."""
    lowered = test_command.lower()
    args: list[str] = []

    if "--maxworkers" not in lowered and "--runinband" not in lowered:
        args.append("--maxWorkers=1")
    if "--pool" not in lowered:
        args.append("--pool=forks")
    if not args:
        return test_command

    return _append_test_args(test_command, args)


def _append_test_args(test_command: str, args: list[str]) -> str:
    """Append CLI args, preserving script-runner passthrough syntax."""
    command = test_command.strip()
    arg_string = " ".join(args)
    normalized = " ".join(command.lower().split())

    if normalized.startswith(("npm run ", "pnpm run ", "bun run ")):
        return f"{command} {arg_string}" if " -- " in command else f"{command} -- {arg_string}"
    return f"{command} {arg_string}"


def run_step(
    name: str,
    command: str,
    cwd: Path,
    timeout: int = DEFAULT_TIMEOUT,
    env: Optional[dict] = None,
) -> StepResult:
    """Execute a single pipeline step as a subprocess.

    Captures stdout, stderr, exit code, and duration.
    Raises no exceptions — always returns a StepResult.
    Timeout is enforced to prevent runaway processes.
    """
    logger.info("Running step '%s': %s (cwd=%s)", name, command, cwd)
    start = time.monotonic()

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            preexec_fn=apply_resource_limits,
        )
        duration = time.monotonic() - start

        step_result = StepResult(
            name=name,
            command=command,
            exit_code=result.returncode,
            duration_seconds=duration,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        step_result = StepResult(
            name=name,
            command=command,
            exit_code=-1,
            duration_seconds=duration,
            stderr=f"Timed out after {timeout} seconds",
        )

    except Exception as exc:
        duration = time.monotonic() - start
        step_result = StepResult(
            name=name,
            command=command,
            exit_code=-2,
            duration_seconds=duration,
            stderr=str(exc),
        )

    status = "OK" if step_result.is_success else "FAILED"
    logger.info(
        "Step '%s' %s (exit=%d, %.1fs)",
        name, status, step_result.exit_code, step_result.duration_seconds,
    )
    if not step_result.is_success:
        if step_result.stderr:
            logger.warning(
                "Step '%s' stderr (tail):\n%s",
                name,
                _truncate_output(step_result.stderr),
            )
        if step_result.stdout:
            logger.warning(
                "Step '%s' stdout (tail):\n%s",
                name,
                _truncate_output(step_result.stdout),
            )

    return step_result


def _truncate_output(text: str, max_lines: int = 60, max_chars: int = 4000) -> str:
    """Return a concise tail of command output for logs."""
    if not text:
        return ""
    lines = text.splitlines()
    tail = lines[-max_lines:]
    joined = "\n".join(tail)
    if len(joined) > max_chars:
        joined = joined[-max_chars:]
    return joined


def run_baseline(
    repo_dir: Path,
    config: DetectionResult,
    bench_cmd: Optional[str] = None,
    execution_mode: Optional[str] = None,
    max_strategy_attempts: Optional[int] = None,
) -> BaselineResult:
    """Execute the full baseline pipeline.

    Pipeline order:
    1. install (critical) — always runs
    2. build (optional) — skipped if no build_cmd detected
    3. typecheck (optional) — skipped if no typecheck_cmd detected
    4. test (critical) — always runs if test_cmd exists
    5. bench (optional) — only if bench_cmd is provided

    Strategy behavior:
    - strict mode: run a single deterministic attempt
    - adaptive mode: run strict first, then bounded fallback attempts
      when failures match known signatures

    Returns a BaselineResult with all step results and strategy metadata.
    """
    repo_dir = Path(repo_dir)
    strategy_settings = StrategySettings.from_values(
        execution_mode=execution_mode,
        max_strategy_attempts=max_strategy_attempts,
    )
    result = run_with_strategy(
        repo_dir=repo_dir,
        detection=config,
        run_step=run_step,
        bench_cmd=bench_cmd,
        strategy_settings=strategy_settings,
        timeout_seconds=DEFAULT_TIMEOUT,
    )
    if not result.is_success and result.error:
        logger.error("Pipeline failed: %s", result.error)
    return result
