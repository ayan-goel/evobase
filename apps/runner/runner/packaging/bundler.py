"""Artifact bundler — assembles pipeline outputs into uploadable bundles.

Creates structured artifacts from baseline results:
- baseline.json: Structured result with step metrics
- logs.txt: Combined stdout/stderr from all steps
- trace.json: Detailed step-by-step execution trace
"""

import json
import logging

from runner.packaging.types import ArtifactBundle
from runner.validator.types import BaselineResult

logger = logging.getLogger(__name__)


def bundle_artifacts(
    run_id: str,
    repo_id: str,
    baseline_result: BaselineResult,
) -> list[ArtifactBundle]:
    """Bundle baseline results into a list of uploadable artifacts.

    Always produces baseline.json, logs.txt, and trace.json.
    Storage paths follow: repos/{repo_id}/runs/{run_id}/{filename}
    """
    path_prefix = f"repos/{repo_id}/runs/{run_id}"
    bundles: list[ArtifactBundle] = []

    # 1. baseline.json — structured result summary
    baseline_json = json.dumps(baseline_result.to_dict(), indent=2)
    bundles.append(ArtifactBundle(
        filename="baseline.json",
        storage_path=f"{path_prefix}/baseline.json",
        content=baseline_json,
        artifact_type="baseline",
    ))

    # 2. logs.txt — combined human-readable log output
    logs = _build_logs(baseline_result)
    bundles.append(ArtifactBundle(
        filename="logs.txt",
        storage_path=f"{path_prefix}/logs.txt",
        content=logs,
        artifact_type="log",
    ))

    # 3. trace.json — detailed execution trace for debugging
    trace = _build_trace(run_id, repo_id, baseline_result)
    trace_json = json.dumps(trace, indent=2)
    bundles.append(ArtifactBundle(
        filename="trace.json",
        storage_path=f"{path_prefix}/trace.json",
        content=trace_json,
        artifact_type="trace",
    ))

    logger.info("Bundled %d artifacts for run %s", len(bundles), run_id)
    return bundles


def _build_logs(result: BaselineResult) -> str:
    """Build a combined log string from all step outputs."""
    sections: list[str] = []

    for step in result.steps:
        header = f"{'=' * 60}\nSTEP: {step.name}\nCOMMAND: {step.command}\nEXIT CODE: {step.exit_code}\nDURATION: {step.duration_seconds:.1f}s\n{'=' * 60}"
        sections.append(header)

        if step.stdout:
            sections.append(f"\n--- stdout ---\n{step.stdout}")
        if step.stderr:
            sections.append(f"\n--- stderr ---\n{step.stderr}")

        sections.append("")

    if result.error:
        sections.append(f"\n{'=' * 60}\nPIPELINE ERROR: {result.error}\n{'=' * 60}")

    return "\n".join(sections)


def _build_trace(
    run_id: str,
    repo_id: str,
    result: BaselineResult,
) -> dict:
    """Build a detailed execution trace for debugging."""
    return {
        "run_id": run_id,
        "repo_id": repo_id,
        "pipeline": {
            "is_success": result.is_success,
            "error": result.error,
            "total_duration_seconds": round(
                sum(s.duration_seconds for s in result.steps), 3
            ),
            "step_count": len(result.steps),
        },
        "steps": [
            {
                "name": s.name,
                "command": s.command,
                "exit_code": s.exit_code,
                "duration_seconds": round(s.duration_seconds, 3),
                "stdout_preview": s.stdout[:500] if s.stdout else "",
                "stderr_preview": s.stderr[:500] if s.stderr else "",
            }
            for s in result.steps
        ],
        "bench_result": result.bench_result,
    }
