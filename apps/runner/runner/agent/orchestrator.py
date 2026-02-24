"""Agent orchestrator — coordinates the full LLM-powered optimization cycle.

Pipeline:
  1. discover_opportunities() — LLM scans repo, returns AgentOpportunity list
  2. For each opportunity, generate_agent_patch() is called once per approach
     string in opportunity.approaches (up to MAX_PATCH_APPROACHES).
  3. run_candidate_validation() — existing pipeline tests each diff
  4. _select_best_variant() — picks the winner by confidence + benchmark delta
  5. Returns all CandidateResult objects (accepted + rejected) for packaging

Budget enforcement:
  - Stops generating patches once max_candidates is reached.
  - Each opportunity counts as one candidate regardless of how many
    approach variants were tried.
  - Approach variants use smart lazy stopping: high-confidence acceptance
    short-circuits immediately; medium/low confidence continues to try
    remaining approaches in case a better patch exists.

All reasoning traces are attached to the returned results so the packaging
layer can store them alongside the validation evidence.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from runner.agent.discovery import discover_opportunities
from runner.agent.patchgen import (
    PatchGenTryRecord,
    PatchGenerationOutcome,
    generate_agent_patch_with_diagnostics,
)
from runner.agent.types import AgentOpportunity, AgentPatch, AgentRun, PatchVariantResult
from runner.detector.types import DetectionResult
from runner.llm.factory import get_provider, validate_model
from runner.llm.types import LLMConfig
from runner.patchgen.types import PatchResult
from runner.validator.candidate import run_candidate_validation
from runner.validator.types import BaselineResult, CandidateResult

logger = logging.getLogger(__name__)

# Default maximum patch attempts per run (overridden by Settings.max_candidates_per_run)
DEFAULT_MAX_CANDIDATES = 12

# Maximum approach variants to try per opportunity
MAX_PATCH_APPROACHES = 3


@dataclass
class AgentCycleResult:
    """Full output of one agent cycle: opportunities, patches, validations."""

    agent_run: AgentRun
    candidate_results: list[CandidateResult] = field(default_factory=list)
    # Parallel index: candidate_results[i] corresponds to agent_run.patches[i]
    opportunity_for_candidate: list[AgentOpportunity] = field(default_factory=list)
    # All approach variants per candidate (including rejected ones)
    patch_variants_for_candidate: list[list[PatchVariantResult]] = field(default_factory=list)
    # Human-readable reason why the winning variant was chosen
    selection_reasons: list[str] = field(default_factory=list)

    @property
    def accepted_count(self) -> int:
        return sum(1 for r in self.candidate_results if r.is_accepted)

    @property
    def total_attempted(self) -> int:
        return len(self.candidate_results)


EventCallback = Callable[[str, str, dict], None]


async def run_agent_cycle(
    repo_dir: Path,
    detection: DetectionResult,
    llm_config: LLMConfig,
    baseline: BaselineResult,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    seen_signatures: frozenset[tuple[str, str]] = frozenset(),
    on_event: Optional[EventCallback] = None,
) -> AgentCycleResult:
    """Run the full LLM agent cycle: discover → patch variants → validate → select.

    Args:
        repo_dir: Absolute path to the checked-out repository.
        detection: Output from Phase 5 detector.
        llm_config: Provider + model + API key configuration.
        baseline: Phase 6 baseline result for comparison.
        max_candidates: Budget cap on validation attempts (per opportunity).
        seen_signatures: Set of (type, file_path) pairs already seen for this
            repo; opportunities matching a signature are skipped before patching.
        on_event: Optional callback invoked as on_event(event_type, phase, data)
            for real-time progress streaming.

    Returns:
        `AgentCycleResult` with all attempts, reasoning traces, and verdicts.
    """
    def _emit(event_type: str, phase: str, data: dict) -> None:
        if on_event:
            try:
                on_event(event_type, phase, data)
            except Exception:
                pass

    repo_dir = Path(repo_dir)

    validate_model(llm_config.provider, llm_config.model)
    provider = get_provider(llm_config.provider)

    agent_run = AgentRun(model=llm_config.model, provider=llm_config.provider)
    result = AgentCycleResult(agent_run=agent_run)

    # Step 1: Discovery
    logger.info(
        "Agent cycle starting: provider=%s model=%s",
        llm_config.provider, llm_config.model,
    )
    opportunities = await discover_opportunities(
        repo_dir=repo_dir,
        detection=detection,
        provider=provider,
        config=llm_config,
        seen_signatures=seen_signatures,
        on_event=on_event,
    )
    agent_run.opportunities = opportunities

    if not opportunities:
        logger.info("No opportunities discovered; agent cycle complete")
        return result

    logger.info("Discovered %d opportunities; generating patches", len(opportunities))

    # Step 2 + 3: Multi-approach patch generation + validation (budget-gated)
    candidates_attempted = 0

    for opp_index, opp in enumerate(opportunities):
        if candidates_attempted >= max_candidates:
            logger.info(
                "Candidate budget exhausted (%d / %d); stopping",
                candidates_attempted, max_candidates,
            )
            break

        approaches = opp.approaches[:MAX_PATCH_APPROACHES] if opp.approaches else [opp.approach]
        if not approaches or not any(approaches):
            logger.debug("Opportunity at %s has no approaches; skipping", opp.location)
            continue

        variants: list[PatchVariantResult] = []

        for idx, approach_desc in enumerate(approaches):
            logger.debug(
                "Generating patch variant %d/%d for %s (approach: %s…)",
                idx + 1, len(approaches), opp.location, approach_desc[:60],
            )
            _emit("patch.approach.started", "patch", {
                "opportunity_index": opp_index,
                "location": opp.location,
                "type": opp.type,
                "approach_index": idx,
                "approach_desc": approach_desc[:120],
                "approach_desc_full": approach_desc,
                "rationale": opp.rationale,
                "risk_level": opp.risk_level,
                "affected_lines": opp.affected_lines,
                "total_approaches": len(approaches),
            })

            patch_outcome = await generate_agent_patch_with_diagnostics(
                opportunity=opp,
                repo_dir=repo_dir,
                provider=provider,
                config=llm_config,
                approach_override=approach_desc,
            )
            patch = patch_outcome.patch

            if patch is None:
                logger.debug(
                    "Patch generation returned None for variant %d at %s",
                    idx, opp.location,
                )
                _emit("patch.approach.completed", "patch", {
                    "opportunity_index": opp_index,
                    "location": opp.location,
                    "type": opp.type,
                    "approach_index": idx,
                    "total_approaches": len(approaches),
                    "approach_desc_full": approach_desc,
                    "success": False,
                    "lines_changed": None,
                    "touched_files": [],
                    "explanation": None,
                    "diff": None,
                    "patch_trace": _trace_to_event_dict(_final_patch_trace(patch_outcome)),
                    "failure_stage": patch_outcome.failure_stage,
                    "failure_reason": patch_outcome.failure_reason,
                    "patchgen_tries": _serialise_patchgen_tries_for_event(patch_outcome.tries),
                })
                candidate_result = _make_error_candidate("Patch generation returned None")
            else:
                _emit("patch.approach.completed", "patch", {
                    "opportunity_index": opp_index,
                    "location": opp.location,
                    "type": opp.type,
                    "approach_index": idx,
                    "total_approaches": len(approaches),
                    "approach_desc_full": approach_desc,
                    "success": True,
                    "lines_changed": patch.estimated_lines_changed,
                    "touched_files": patch.touched_files,
                    "explanation": patch.explanation,
                    "diff": patch.diff,
                    "patch_trace": _trace_to_event_dict(_final_patch_trace(patch_outcome)),
                    "failure_stage": None,
                    "failure_reason": None,
                    "patchgen_tries": _serialise_patchgen_tries_for_event(patch_outcome.tries),
                })
                proxy_patch = PatchResult(
                    diff=patch.diff,
                    explanation=patch.explanation,
                    touched_files=patch.touched_files,
                    template_name="llm_agent",
                    lines_changed=patch.estimated_lines_changed,
                )
                _emit("validation.candidate.started", "validation", {
                    "candidate_index": candidates_attempted,
                    "location": opp.location,
                    "approach_index": idx,
                })
                try:
                    candidate_result = run_candidate_validation(
                        repo_dir=repo_dir,
                        config=detection,
                        patch=proxy_patch,
                        baseline=baseline,
                    )
                except Exception as exc:
                    logger.error(
                        "Validation raised for variant %d at %s: %s",
                        idx, opp.location, exc,
                    )
                    candidate_result = _make_error_candidate(str(exc))

            variants.append(PatchVariantResult(
                approach_index=idx,
                approach_description=approach_desc,
                patch=patch,
                candidate_result=candidate_result,
            ))

            # Smart lazy stopping: stop immediately only on high-confidence acceptance.
            # For medium/low confidence, continue trying remaining approaches — a later
            # variant may produce a better patch, improving proposal quality.
            if candidate_result.is_accepted:
                is_high_confidence = (
                    candidate_result.final_verdict is not None
                    and candidate_result.final_verdict.confidence == "high"
                )
                if is_high_confidence:
                    logger.debug(
                        "High-confidence accepted variant %d; skipping remaining approach variants",
                        idx,
                    )
                    break
                logger.debug(
                    "Medium/low-confidence accepted variant %d; trying remaining approaches for a better patch",
                    idx,
                )

        # Select the best variant
        winner_idx, selection_reason = _select_best_variant(variants)

        if winner_idx < 0:
            # All approaches failed; still record for traceability
            for v in variants:
                v.selection_reason = "rejected"
            # Use the first variant's result as the candidate (will be is_accepted=False)
            winner_candidate = variants[0].candidate_result if variants else _make_error_candidate("no variants")
            winning_patch = variants[0].patch if variants else None
        else:
            variants[winner_idx].is_selected = True
            variants[winner_idx].selection_reason = selection_reason
            winner_candidate = variants[winner_idx].candidate_result
            winning_patch = variants[winner_idx].patch

        # Emit verdict and selection events immediately after this candidate is resolved
        _emit("validation.verdict", "validation", {
            "index": candidates_attempted,
            "opportunity": opp.location,
            "accepted": winner_candidate.is_accepted,
            "confidence": winner_candidate.final_verdict.confidence if winner_candidate.final_verdict else None,
            "reason": winner_candidate.final_verdict.reason if winner_candidate.final_verdict else None,
            "gates_passed": winner_candidate.final_verdict.gates_passed if winner_candidate.final_verdict else [],
            "gates_failed": winner_candidate.final_verdict.gates_failed if winner_candidate.final_verdict else [],
            "approaches_tried": len(variants),
            "attempts": _serialise_validation_attempts_for_event(winner_candidate),
            "benchmark_comparison": (
                winner_candidate.final_verdict.benchmark_comparison.to_dict()
                if winner_candidate.final_verdict and winner_candidate.final_verdict.benchmark_comparison
                else None
            ),
        })
        if winner_candidate.is_accepted and selection_reason:
            _emit("selection.completed", "selection", {
                "index": candidates_attempted,
                "reason": selection_reason,
                # LLM-generated acceptance verdict — more meaningful than confidence label
                "verdict_reason": (
                    winner_candidate.final_verdict.reason
                    if winner_candidate.final_verdict
                    else None
                ),
                "patch_title": winning_patch.title if winning_patch and winning_patch.title else None,
            })

        agent_run.patches.append(winning_patch)
        agent_run.errors.append(None if winning_patch else "No valid patch")

        result.candidate_results.append(winner_candidate)
        result.opportunity_for_candidate.append(opp)
        result.patch_variants_for_candidate.append(variants)
        result.selection_reasons.append(selection_reason)
        candidates_attempted += 1

        logger.info(
            "Candidate %d/%d at %s: accepted=%s variants_tried=%d reason=%s",
            candidates_attempted, max_candidates,
            opp.location, winner_candidate.is_accepted, len(variants), selection_reason,
        )

    logger.info(
        "Agent cycle complete: %d attempted, %d accepted",
        result.total_attempted, result.accepted_count,
    )
    return result


def _select_best_variant(
    variants: list[PatchVariantResult],
) -> tuple[int, str]:
    """Pick the best patch variant from the list.

    Selection priority:
      1. Accepted over rejected
      2. Higher confidence ("high" > "medium" > "low")
      3. Greater benchmark improvement percentage

    Returns:
        (winner_index, human_readable_reason) where winner_index is -1 when
        all variants failed validation.
    """
    if not variants:
        return -1, "no variants generated"

    accepted = [
        (i, v) for i, v in enumerate(variants)
        if v.candidate_result and v.candidate_result.is_accepted
    ]

    if not accepted:
        return -1, "no accepted approaches"

    def sort_key(item: tuple[int, PatchVariantResult]) -> tuple[int, float]:
        _, v = item
        conf_rank = _confidence_rank(v.candidate_result)
        bench_pct = 0.0
        if (
            v.candidate_result.final_verdict
            and v.candidate_result.final_verdict.benchmark_comparison
        ):
            bench_pct = v.candidate_result.final_verdict.benchmark_comparison.improvement_pct
        return (conf_rank, bench_pct)

    accepted.sort(key=sort_key, reverse=True)
    winner_idx, winner = accepted[0]
    reason = _build_selection_reason(winner, len(accepted), len(variants))
    return winner_idx, reason


def _confidence_rank(candidate: CandidateResult) -> int:
    """Map confidence string to a sortable integer."""
    if not candidate.final_verdict:
        return 0
    return {"high": 2, "medium": 1, "low": 0}.get(candidate.final_verdict.confidence, 0)


def _build_selection_reason(
    winner: PatchVariantResult,
    accepted_count: int,
    total_count: int,
) -> str:
    """Build a human-readable reason string for why this variant was chosen."""
    if not winner.candidate_result.final_verdict:
        return "accepted approach"

    verdict = winner.candidate_result.final_verdict
    parts: list[str] = []

    conf = verdict.confidence
    if conf == "high":
        parts.append("high confidence")
    elif conf == "medium":
        parts.append("medium confidence")
    else:
        parts.append("low confidence")

    if verdict.benchmark_comparison and verdict.benchmark_comparison.is_significant:
        pct = verdict.benchmark_comparison.improvement_pct
        parts.append(f"{pct:.1f}% benchmark improvement")

    if accepted_count < total_count:
        rejected = total_count - accepted_count
        parts.append(f"{rejected} other approach{'es' if rejected > 1 else ''} rejected")

    return "; ".join(parts) if parts else "accepted approach"


def _make_error_candidate(error_msg: str) -> CandidateResult:
    """Return a synthetic failed CandidateResult for error cases."""
    from runner.validator.types import AcceptanceVerdict, AttemptRecord, CONFIDENCE_LOW

    verdict = AcceptanceVerdict(
        is_accepted=False,
        confidence=CONFIDENCE_LOW,
        reason=f"Validation error: {error_msg}",
        gates_failed=["exception"],
    )
    attempt = AttemptRecord(
        attempt_number=1,
        patch_applied=False,
        pipeline_result=None,
        verdict=verdict,
        error=error_msg,
    )
    return CandidateResult(
        attempts=[attempt],
        final_verdict=verdict,
        is_accepted=False,
    )


def _trace_to_event_dict(trace) -> Optional[dict]:
    """Serialise a ThinkingTrace-like object to the run event payload."""
    if not trace:
        return None
    try:
        return trace.to_dict()
    except Exception:
        return None


def _final_patch_trace(outcome: PatchGenerationOutcome):
    if outcome.patch and outcome.patch.thinking_trace:
        return outcome.patch.thinking_trace
    if outcome.tries:
        last_try = outcome.tries[-1]
        if last_try.patch and last_try.patch.thinking_trace:
            return last_try.patch.thinking_trace
        return last_try.patch_trace
    return None


def _serialise_patchgen_tries_for_event(tries: list[PatchGenTryRecord]) -> list[dict]:
    payload: list[dict] = []
    for t in tries:
        patch = t.patch
        trace = patch.thinking_trace if patch and patch.thinking_trace else t.patch_trace
        payload.append({
            "attempt_number": t.attempt_number,
            "success": t.success,
            "failure_stage": t.failure_stage,
            "failure_reason": t.failure_reason,
            "diff": patch.diff if patch else None,
            "explanation": patch.explanation if patch else None,
            "touched_files": patch.touched_files if patch else [],
            "estimated_lines_changed": patch.estimated_lines_changed if patch else 0,
            "patch_trace": _trace_to_event_dict(trace),
        })
    return payload


def _serialise_validation_attempts_for_event(candidate: CandidateResult) -> list[dict]:
    payload: list[dict] = []
    for attempt in candidate.attempts:
        steps = []
        if attempt.pipeline_result:
            steps = [step.to_dict() for step in attempt.pipeline_result.steps]
        payload.append({
            "attempt_number": attempt.attempt_number,
            "patch_applied": attempt.patch_applied,
            "error": attempt.error,
            "timestamp": attempt.timestamp,
            "steps": steps,
            "verdict": attempt.verdict.to_dict() if attempt.verdict else None,
        })
    return payload
