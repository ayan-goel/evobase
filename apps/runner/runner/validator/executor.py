"""Baseline execution pipeline.

Runs install -> build -> typecheck -> test -> bench in sequence.
Critical steps (install, test) fail the entire pipeline.
Optional steps (build, typecheck, bench) are logged but don't block.

Each step runs as a subprocess with timeout enforcement and full
stdout/stderr capture for artifact storage.
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

from runner.detector.types import DetectionResult
from runner.sandbox.limits import apply_resource_limits
from runner.validator.types import BaselineResult, PipelineError, StepResult

logger = logging.getLogger(__name__)

# Steps that abort the pipeline on failure
CRITICAL_STEPS = {"install", "test"}

# Default timeout per step (seconds)
DEFAULT_TIMEOUT = 300


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

    return step_result


def run_baseline(
    repo_dir: Path,
    config: DetectionResult,
    bench_cmd: Optional[str] = None,
) -> BaselineResult:
    """Execute the full baseline pipeline.

    Pipeline order:
    1. install (critical) — always runs
    2. build (optional) — skipped if no build_cmd detected
    3. typecheck (optional) — skipped if no typecheck_cmd detected
    4. test (critical) — always runs if test_cmd exists
    5. bench (optional) — only if bench_cmd is provided

    Returns a BaselineResult with all step results.
    Raises PipelineError if a critical step fails.
    """
    result = BaselineResult()
    repo_dir = Path(repo_dir)

    try:
        # 1. Install (critical)
        install_step = run_step("install", config.install_cmd or "npm ci", repo_dir)
        result.steps.append(install_step)

        if not install_step.is_success:
            raise PipelineError(install_step)

        # 2. Build (optional)
        if config.build_cmd:
            build_step = run_step("build", config.build_cmd, repo_dir)
            result.steps.append(build_step)

            if not build_step.is_success:
                logger.warning("Build failed but is non-critical; continuing")

        # 3. Typecheck (optional)
        if config.typecheck_cmd:
            typecheck_step = run_step("typecheck", config.typecheck_cmd, repo_dir)
            result.steps.append(typecheck_step)

            if not typecheck_step.is_success:
                logger.warning("Typecheck failed but is non-critical; continuing")

        # 4. Test (critical)
        if config.test_cmd:
            test_step = run_step("test", config.test_cmd, repo_dir)
            result.steps.append(test_step)

            if not test_step.is_success:
                raise PipelineError(test_step)

        # 5. Bench (optional)
        if bench_cmd:
            bench_step = run_step("bench", bench_cmd, repo_dir)
            result.steps.append(bench_step)

            if bench_step.is_success:
                result.bench_result = {
                    "command": bench_cmd,
                    "stdout": bench_step.stdout,
                    "duration_seconds": bench_step.duration_seconds,
                }
            else:
                logger.warning("Bench failed but is non-critical; continuing")

        result.is_success = True

    except PipelineError as exc:
        result.is_success = False
        result.error = str(exc)
        logger.error("Pipeline failed: %s", exc)

    return result
