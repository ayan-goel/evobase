"""Strict-then-adaptive strategy engine for baseline execution."""

import json
import logging
import os
from dataclasses import replace
from pathlib import Path
from typing import Callable, Optional

from runner.detector.types import DetectionResult
from runner.execution.failure_classifier import classify_pipeline_failure
from runner.execution.strategy_types import (
    AttemptMode,
    EcosystemAdapter,
    ExecutionAttemptPlan,
    ExecutionContext,
    ExecutionMode,
    FailureReasonCode,
    StepFailure,
    StrategySettings,
)
from runner.validator.types import BaselineResult, PipelineError, StepResult

logger = logging.getLogger(__name__)


StepRunner = Callable[..., StepResult]


def run_with_strategy(
    repo_dir: Path,
    detection: DetectionResult,
    run_step: StepRunner,
    bench_cmd: Optional[str] = None,
    strategy_settings: Optional[StrategySettings] = None,
    timeout_seconds: int = 300,
) -> BaselineResult:
    """Run baseline with a strict-first strategy and bounded adaptive fallback."""
    settings = strategy_settings or StrategySettings()
    context = ExecutionContext(
        repo_dir=Path(repo_dir),
        detection=detection,
        bench_command=bench_cmd,
        settings=settings,
    )

    adapter = _resolve_adapter(detection)
    attempt_plan = adapter.build_strict_plan(context)
    attempt_plan = replace(attempt_plan, attempt_number=1, mode=AttemptMode.STRICT)

    last_result: Optional[BaselineResult] = None
    for attempt_number in range(1, settings.max_attempts + 1):
        if attempt_number > 1:
            assert last_result is not None  # for static analyzers
            failure = classify_pipeline_failure(last_result)
            if settings.mode == ExecutionMode.STRICT:
                return last_result

            adaptive_plan = adapter.build_adaptive_plan(context, attempt_plan, failure)
            if adaptive_plan is None:
                return last_result
            attempt_plan = replace(
                adaptive_plan,
                attempt_number=attempt_number,
                mode=AttemptMode.ADAPTIVE,
            )

        logger.info(
            "Baseline strategy attempt %d/%d mode=%s install=%s test=%s",
            attempt_number,
            settings.max_attempts,
            attempt_plan.mode.value,
            attempt_plan.install_command,
            attempt_plan.test_command,
        )
        result = _execute_attempt(
            repo_dir=context.repo_dir,
            plan=attempt_plan,
            run_step=run_step,
            timeout_seconds=timeout_seconds,
        )
        result.strategy_attempts = attempt_number
        result.strategy_mode = attempt_plan.mode.value
        if result.is_success:
            return result

        failure = classify_pipeline_failure(result)
        result.failure_reason_code = failure.reason_code.value
        if attempt_plan.mode == AttemptMode.ADAPTIVE:
            result.adaptive_transition_reason = (
                attempt_plan.metadata.get("adaptive_reason") or failure.reason_code.value
            )
        last_result = result

    return last_result or BaselineResult(
        is_success=False,
        error="Strategy engine executed no attempts",
    )


def _execute_attempt(
    repo_dir: Path,
    plan: ExecutionAttemptPlan,
    run_step: StepRunner,
    timeout_seconds: int,
) -> BaselineResult:
    """Execute one baseline attempt plan."""
    result = BaselineResult()
    try:
        install_step = run_step(
            "install",
            plan.install_command,
            repo_dir,
            timeout=timeout_seconds,
            env=plan.install_env,
        )
        result.steps.append(install_step)
        if not install_step.is_success:
            raise PipelineError(install_step)

        if plan.build_command:
            build_step = run_step(
                "build",
                plan.build_command,
                repo_dir,
                timeout=timeout_seconds,
            )
            result.steps.append(build_step)
            if not build_step.is_success:
                logger.warning("Build failed but is non-critical; continuing")

        if plan.typecheck_command:
            typecheck_step = run_step(
                "typecheck",
                plan.typecheck_command,
                repo_dir,
                timeout=timeout_seconds,
            )
            result.steps.append(typecheck_step)
            if not typecheck_step.is_success:
                logger.warning("Typecheck failed but is non-critical; continuing")

        if plan.test_command:
            test_step = run_step(
                "test",
                plan.test_command,
                repo_dir,
                timeout=timeout_seconds,
                env=plan.test_env,
            )
            result.steps.append(test_step)
            if not test_step.is_success:
                raise PipelineError(test_step)

        if plan.bench_command:
            bench_step = run_step(
                "bench",
                plan.bench_command,
                repo_dir,
                timeout=timeout_seconds,
            )
            result.steps.append(bench_step)
            if bench_step.is_success:
                result.bench_result = {
                    "command": plan.bench_command,
                    "stdout": bench_step.stdout,
                    "duration_seconds": bench_step.duration_seconds,
                }
            else:
                logger.warning("Bench failed but is non-critical; continuing")

        result.is_success = True
        return result
    except PipelineError as exc:
        result.is_success = False
        result.error = str(exc)
        return result


class BaseAdapter:
    """Default adapter: deterministic strict plan with no adaptive retry."""

    def build_strict_plan(self, context: ExecutionContext) -> ExecutionAttemptPlan:
        detection = context.detection
        install_command = detection.install_cmd or _fallback_install_command(detection)
        return ExecutionAttemptPlan(
            attempt_number=1,
            mode=AttemptMode.STRICT,
            install_command=install_command,
            build_command=detection.build_cmd,
            typecheck_command=detection.typecheck_cmd,
            test_command=detection.test_cmd,
            bench_command=context.bench_command,
            install_env=None,
            test_env=None,
            metadata={},
        )

    def build_adaptive_plan(
        self,
        context: ExecutionContext,
        previous_plan: ExecutionAttemptPlan,
        failure: StepFailure,
    ) -> Optional[ExecutionAttemptPlan]:
        return None


class NodeAdapter(BaseAdapter):
    """Node adapter with strict lockfile mode and adaptive retries."""

    def build_strict_plan(self, context: ExecutionContext) -> ExecutionAttemptPlan:
        plan = super().build_strict_plan(context)
        return replace(
            plan,
            install_env=_js_install_env(),
            test_env=_js_test_env(),
        )

    def build_adaptive_plan(
        self,
        context: ExecutionContext,
        previous_plan: ExecutionAttemptPlan,
        failure: StepFailure,
    ) -> Optional[ExecutionAttemptPlan]:
        if failure.step_name == "install" and failure.reason_code in {
            FailureReasonCode.LOCKFILE_DRIFT,
            FailureReasonCode.MISSING_DEV_DEPENDENCIES,
        }:
            relaxed_install = _relax_node_install_command(
                previous_plan.install_command,
                context.detection.package_manager or "npm",
            )
            if relaxed_install == previous_plan.install_command:
                return None
            return replace(
                previous_plan,
                install_command=relaxed_install,
                install_env=_js_install_env(),
                metadata={"adaptive_reason": failure.reason_code.value},
            )

        if failure.step_name == "test" and failure.reason_code in {
            FailureReasonCode.CONCURRENCY_OOM,
            FailureReasonCode.OOM,
        }:
            if not previous_plan.test_command:
                return None
            if not _is_vitest_command(context.repo_dir, previous_plan.test_command):
                return None
            throttled_test = _append_vitest_throttle_flags(previous_plan.test_command)
            if throttled_test == previous_plan.test_command:
                return None
            return replace(
                previous_plan,
                test_command=throttled_test,
                test_env=_js_test_env(),
                metadata={"adaptive_reason": failure.reason_code.value},
            )

        return None


class PythonAdapter(BaseAdapter):
    """Python adapter with conservative fallback for missing wrappers."""

    def build_strict_plan(self, context: ExecutionContext) -> ExecutionAttemptPlan:
        return super().build_strict_plan(context)

    def build_adaptive_plan(
        self,
        context: ExecutionContext,
        previous_plan: ExecutionAttemptPlan,
        failure: StepFailure,
    ) -> Optional[ExecutionAttemptPlan]:
        if failure.step_name != "install":
            return None
        if failure.reason_code not in {
            FailureReasonCode.COMMAND_NOT_FOUND,
            FailureReasonCode.WRAPPER_MISSING,
        }:
            return None

        fallback_requirements = context.repo_dir / "requirements.txt"
        if not fallback_requirements.exists():
            return None
        if previous_plan.install_command.strip() == "pip install -r requirements.txt":
            return None
        return replace(
            previous_plan,
            install_command="pip install -r requirements.txt",
            metadata={"adaptive_reason": failure.reason_code.value},
        )


class RubyAdapter(BaseAdapter):
    """Ruby adapter with bundler environment normalization."""

    def build_strict_plan(self, context: ExecutionContext) -> ExecutionAttemptPlan:
        plan = super().build_strict_plan(context)
        return replace(plan, install_env=_bundler_install_env())


class GoAdapter(BaseAdapter):
    """Go adapter with optional module graph refresh fallback."""

    def build_adaptive_plan(
        self,
        context: ExecutionContext,
        previous_plan: ExecutionAttemptPlan,
        failure: StepFailure,
    ) -> Optional[ExecutionAttemptPlan]:
        if failure.step_name != "install":
            return None
        if failure.reason_code not in {
            FailureReasonCode.INSTALL_FAILED,
            FailureReasonCode.COMMAND_NOT_FOUND,
        }:
            return None
        if "go mod tidy" in previous_plan.install_command:
            return None
        return replace(
            previous_plan,
            install_command="go mod tidy && go mod download",
            metadata={"adaptive_reason": failure.reason_code.value},
        )


class RustAdapter(BaseAdapter):
    """Rust adapter with lock refresh fallback."""

    def build_adaptive_plan(
        self,
        context: ExecutionContext,
        previous_plan: ExecutionAttemptPlan,
        failure: StepFailure,
    ) -> Optional[ExecutionAttemptPlan]:
        if failure.step_name != "install":
            return None
        if failure.reason_code != FailureReasonCode.INSTALL_FAILED:
            return None
        if "cargo update" in previous_plan.install_command:
            return None
        return replace(
            previous_plan,
            install_command="cargo update && cargo fetch",
            metadata={"adaptive_reason": failure.reason_code.value},
        )


class JvmAdapter(BaseAdapter):
    """JVM adapter with wrapper-missing fallback to system toolchains."""

    def build_adaptive_plan(
        self,
        context: ExecutionContext,
        previous_plan: ExecutionAttemptPlan,
        failure: StepFailure,
    ) -> Optional[ExecutionAttemptPlan]:
        if failure.reason_code != FailureReasonCode.WRAPPER_MISSING:
            return None

        mapped = _replace_jvm_wrapper_commands(previous_plan)
        if mapped == previous_plan:
            return None
        return replace(
            mapped,
            metadata={"adaptive_reason": failure.reason_code.value},
        )


def _replace_jvm_wrapper_commands(plan: ExecutionAttemptPlan) -> ExecutionAttemptPlan:
    return replace(
        plan,
        install_command=_replace_wrapper_command(plan.install_command),
        build_command=_replace_wrapper_command(plan.build_command),
        typecheck_command=_replace_wrapper_command(plan.typecheck_command),
        test_command=_replace_wrapper_command(plan.test_command),
    )


def _replace_wrapper_command(command: Optional[str]) -> Optional[str]:
    if not command:
        return command
    replaced = command.replace("./mvnw", "mvn").replace("./gradlew", "gradle")
    return replaced


def _resolve_adapter(detection: DetectionResult) -> EcosystemAdapter:
    language = (detection.language or "").lower()
    package_manager = (detection.package_manager or "").lower()

    if language == "javascript" or package_manager in {"npm", "pnpm", "yarn", "bun"}:
        return NodeAdapter()
    if language == "python" or package_manager in {"pip", "poetry", "pipenv", "uv"}:
        return PythonAdapter()
    if language == "ruby" or package_manager == "bundler":
        return RubyAdapter()
    if language == "go" or package_manager == "go":
        return GoAdapter()
    if language == "rust" or package_manager == "cargo":
        return RustAdapter()
    if language == "java" or package_manager in {"maven", "gradle"}:
        return JvmAdapter()
    return BaseAdapter()


def _fallback_install_command(detection: DetectionResult) -> str:
    pm = (detection.package_manager or "").lower()
    if pm == "pnpm":
        return "pnpm install --frozen-lockfile"
    if pm == "yarn":
        return "yarn install --frozen-lockfile"
    if pm == "bun":
        return "bun install --frozen-lockfile"
    if pm == "pip":
        return "pip install -r requirements.txt"
    if pm == "poetry":
        return "poetry install"
    if pm == "pipenv":
        return "pipenv install --dev"
    if pm == "uv":
        return "uv sync --dev"
    if pm == "bundler":
        return "bundle install"
    if pm == "go":
        return "go mod download"
    if pm == "cargo":
        return "cargo fetch"
    if pm == "maven":
        return "mvn -q -DskipTests install"
    if pm == "gradle":
        return "./gradlew assemble -q"
    # Last-resort fallback for unknown repos.
    return "npm ci"


def _js_install_env() -> dict:
    env = dict(os.environ)
    env["NODE_ENV"] = "development"
    env["NPM_CONFIG_PRODUCTION"] = "false"
    return env


def _js_test_env() -> dict:
    env = dict(os.environ)
    env["CI"] = "true"
    return env


def _bundler_install_env() -> dict:
    env = dict(os.environ)
    env["BUNDLE_DEPLOYMENT"] = "false"
    env["BUNDLE_FROZEN"] = "false"
    env["BUNDLE_WITHOUT"] = ""
    return env


def _is_vitest_command(repo_dir: Path, test_command: str) -> bool:
    lowered = test_command.lower()
    if "vitest" in lowered:
        return True
    if not _is_js_test_script_command(test_command):
        return False
    script = _read_package_json_test_script(repo_dir)
    return bool(script and "vitest" in script.lower())


def _is_js_test_script_command(command: str) -> bool:
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
    command = test_command.strip()
    arg_string = " ".join(args)
    normalized = " ".join(command.lower().split())

    if normalized.startswith(("npm run ", "pnpm run ", "bun run ")):
        return f"{command} {arg_string}" if " -- " in command else f"{command} -- {arg_string}"
    return f"{command} {arg_string}"


def _relax_node_install_command(command: str, package_manager: str) -> str:
    normalized = command.strip()
    pm = package_manager.lower()

    if pm == "npm" and normalized.startswith("npm ci"):
        return normalized.replace("npm ci", "npm install", 1)
    if pm == "pnpm" and "--frozen-lockfile" in normalized:
        return normalized.replace(" --frozen-lockfile", "")
    if pm == "yarn" and "--frozen-lockfile" in normalized:
        return normalized.replace(" --frozen-lockfile", "")
    if pm == "bun" and "--frozen-lockfile" in normalized:
        return normalized.replace(" --frozen-lockfile", "")
    return normalized
