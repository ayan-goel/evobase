"""Proposal bundler — assembles full evidence bundles for accepted patches.

Produces three artifacts per accepted proposal:
  proposal.json  — canonical proposal schema with all evidence fields
  diff.patch     — raw unified diff as a text file for direct download
  trace.json     — attempt-by-attempt validation timeline

The proposal.json schema is the single source of truth consumed by the
API's POST /proposals/create endpoint and displayed in the frontend diff viewer.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from runner.packaging.types import ArtifactBundle
from runner.patchgen.types import PatchResult
from runner.scanner.types import Opportunity
from runner.validator.types import BaselineResult, CandidateResult

logger = logging.getLogger(__name__)

# Canonical schema version — increment when the shape changes
PROPOSAL_SCHEMA_VERSION = "1.0"


def bundle_proposal(
    run_id: str,
    repo_id: str,
    opportunity: Opportunity,
    patch: PatchResult,
    baseline: BaselineResult,
    candidate: CandidateResult,
) -> list[ArtifactBundle]:
    """Build the complete artifact bundle for an accepted proposal.

    Returns three ArtifactBundle objects for proposal.json, diff.patch,
    and trace.json. The caller is responsible for uploading these via the
    API after creating the Proposal record.

    Args:
        run_id: UUID string of the current optimization run.
        repo_id: UUID string of the repository being optimized.
        opportunity: The scanner opportunity that triggered this proposal.
        patch: The generated patch (diff, explanation, constraint metadata).
        baseline: The pre-patch pipeline result for comparison.
        candidate: The post-patch validation results with acceptance verdict.
    """
    if not candidate.is_accepted:
        logger.warning(
            "bundle_proposal called for a non-accepted candidate (run=%s); "
            "bundling anyway for debugging purposes",
            run_id,
        )

    path_prefix = f"repos/{repo_id}/runs/{run_id}"
    bundles: list[ArtifactBundle] = []

    # 1. proposal.json — canonical proposal schema
    proposal_data = _build_proposal_schema(
        run_id=run_id,
        repo_id=repo_id,
        opportunity=opportunity,
        patch=patch,
        baseline=baseline,
        candidate=candidate,
    )
    bundles.append(ArtifactBundle(
        filename="proposal.json",
        storage_path=f"{path_prefix}/proposal.json",
        content=json.dumps(proposal_data, indent=2),
        artifact_type="proposal",
    ))

    # 2. diff.patch — raw diff for direct download / apply
    bundles.append(ArtifactBundle(
        filename="diff.patch",
        storage_path=f"{path_prefix}/diff.patch",
        content=patch.diff,
        artifact_type="diff",
    ))

    # 3. trace.json — attempt-by-attempt validation timeline
    trace_data = _build_trace(
        run_id=run_id,
        repo_id=repo_id,
        opportunity=opportunity,
        patch=patch,
        candidate=candidate,
    )
    bundles.append(ArtifactBundle(
        filename="trace.json",
        storage_path=f"{path_prefix}/trace.json",
        content=json.dumps(trace_data, indent=2),
        artifact_type="trace",
    ))

    logger.info(
        "Bundled %d proposal artifacts for run %s (opportunity=%s)",
        len(bundles), run_id, opportunity.type,
    )
    return bundles


def extract_metrics(result: BaselineResult) -> dict:
    """Extract serializable pipeline metrics from a BaselineResult.

    Used for both metrics_before and metrics_after in the proposal schema.
    Only includes timing and step-level outcomes — no raw output (too large).
    """
    return {
        "is_success": result.is_success,
        "total_duration_seconds": round(
            sum(s.duration_seconds for s in result.steps), 3
        ),
        "step_count": len(result.steps),
        "steps": [
            {
                "name": s.name,
                "exit_code": s.exit_code,
                "duration_seconds": round(s.duration_seconds, 3),
                "is_success": s.is_success,
            }
            for s in result.steps
        ],
        "bench_result": result.bench_result,
        "error": result.error,
    }


def _build_proposal_schema(
    run_id: str,
    repo_id: str,
    opportunity: Opportunity,
    patch: PatchResult,
    baseline: BaselineResult,
    candidate: CandidateResult,
) -> dict:
    """Build the full canonical proposal.json schema."""
    verdict = candidate.final_verdict
    candidate_pipeline = _get_candidate_pipeline(candidate)

    return {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "repo_id": repo_id,

        # Opportunity that triggered the proposal
        "opportunity": opportunity.to_dict(),

        # Patch metadata (not the full diff — that's in diff.patch)
        "patch": {
            "template_name": patch.template_name,
            "explanation": patch.explanation,
            "touched_files": patch.touched_files,
            "lines_changed": patch.lines_changed,
            "diff_preview": patch.diff[:500] + ("..." if len(patch.diff) > 500 else ""),
        },

        # Human-readable summary for the PR description
        "summary": _build_summary(opportunity, patch),

        # Acceptance outcome
        "confidence": verdict.confidence if verdict else "low",
        "is_accepted": candidate.is_accepted,
        "acceptance_verdict": verdict.to_dict() if verdict else None,

        # Comparative metrics for the PR body / diff viewer
        "metrics_before": extract_metrics(baseline),
        "metrics_after": extract_metrics(candidate_pipeline) if candidate_pipeline else None,

        # Full attempt trace for debugging / evidence viewer
        "trace_timeline": [a.to_dict() for a in candidate.attempts],
    }


def _build_trace(
    run_id: str,
    repo_id: str,
    opportunity: Opportunity,
    patch: PatchResult,
    candidate: CandidateResult,
) -> dict:
    """Build the trace.json artifact: attempt-level validation timeline."""
    return {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "run_id": run_id,
        "repo_id": repo_id,
        "opportunity_type": opportunity.type,
        "opportunity_location": opportunity.location,
        "template_name": patch.template_name,
        "total_attempts": len(candidate.attempts),
        "is_accepted": candidate.is_accepted,
        "final_verdict": candidate.final_verdict.to_dict() if candidate.final_verdict else None,
        "attempts": [
            {
                "attempt_number": a.attempt_number,
                "patch_applied": a.patch_applied,
                "timestamp": a.timestamp,
                "error": a.error,
                "steps": (
                    [s.to_dict() for s in a.pipeline_result.steps]
                    if a.pipeline_result
                    else []
                ),
                "verdict": a.verdict.to_dict() if a.verdict else None,
            }
            for a in candidate.attempts
        ],
    }


def _get_candidate_pipeline(candidate: CandidateResult) -> Optional[BaselineResult]:
    """Return the pipeline result from the final decisive attempt."""
    if not candidate.attempts:
        return None
    # The last attempt is the decisive one (may be the flaky rerun)
    return candidate.attempts[-1].pipeline_result


def _build_summary(opportunity: Opportunity, patch: PatchResult) -> str:
    """Build a concise human-readable summary for the proposal."""
    location_short = opportunity.location.rsplit("/", 1)[-1]
    return (
        f"{patch.explanation.split('.')[0]} in {location_short}."
    )
