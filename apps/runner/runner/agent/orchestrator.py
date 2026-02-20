"""Agent orchestrator — coordinates the full LLM-powered optimization cycle.

Pipeline:
  1. discover_opportunities() — LLM scans repo, returns AgentOpportunity list
  2. generate_agent_patch() — LLM generates a diff for each opportunity
  3. run_candidate_validation() — existing Phase 9 pipeline tests each diff
  4. Returns all CandidateResult objects (accepted + rejected) for packaging

Budget enforcement:
  - Stops generating patches once max_candidates is reached.
  - Skips high-risk opportunities if the budget is nearly exhausted.

All reasoning traces are attached to the returned results so the packaging
layer can store them alongside the validation evidence.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from runner.agent.discovery import discover_opportunities
from runner.agent.patchgen import generate_agent_patch
from runner.agent.types import AgentOpportunity, AgentPatch, AgentRun
from runner.detector.types import DetectionResult
from runner.llm.factory import get_provider, validate_model
from runner.llm.types import LLMConfig
from runner.patchgen.types import PatchResult
from runner.validator.candidate import run_candidate_validation
from runner.validator.types import BaselineResult, CandidateResult

logger = logging.getLogger(__name__)

# Default maximum patch attempts per run (overridden by Settings.max_candidates_per_run)
DEFAULT_MAX_CANDIDATES = 20


@dataclass
class AgentCycleResult:
    """Full output of one agent cycle: opportunities, patches, validations."""

    agent_run: AgentRun
    candidate_results: list[CandidateResult] = field(default_factory=list)
    # Parallel index: candidate_results[i] corresponds to agent_run.patches[i]
    opportunity_for_candidate: list[AgentOpportunity] = field(default_factory=list)

    @property
    def accepted_count(self) -> int:
        return sum(1 for r in self.candidate_results if r.is_accepted)

    @property
    def total_attempted(self) -> int:
        return len(self.candidate_results)


async def run_agent_cycle(
    repo_dir: Path,
    detection: DetectionResult,
    llm_config: LLMConfig,
    baseline: BaselineResult,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    seen_signatures: frozenset[tuple[str, str]] = frozenset(),
) -> AgentCycleResult:
    """Run the full LLM agent cycle: discover → patch → validate.

    Args:
        repo_dir: Absolute path to the checked-out repository.
        detection: Output from Phase 5 detector.
        llm_config: Provider + model + API key configuration.
        baseline: Phase 6 baseline result for comparison.
        max_candidates: Budget cap on validation attempts.
        seen_signatures: Set of (type, file_path) pairs already seen for this
            repo; opportunities matching a signature are skipped before patching.

    Returns:
        `AgentCycleResult` with all attempts, reasoning traces, and verdicts.
    """
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
    )
    agent_run.opportunities = opportunities

    if not opportunities:
        logger.info("No opportunities discovered; agent cycle complete")
        return result

    logger.info("Discovered %d opportunities; generating patches", len(opportunities))

    # Step 2 + 3: Patch generation + validation (sequential, budget-gated)
    candidates_attempted = 0

    for opp in opportunities:
        if candidates_attempted >= max_candidates:
            logger.info(
                "Candidate budget exhausted (%d / %d); stopping",
                candidates_attempted, max_candidates,
            )
            break

        # Generate patch
        patch = await generate_agent_patch(
            opportunity=opp,
            repo_dir=repo_dir,
            provider=provider,
            config=llm_config,
        )
        agent_run.patches.append(patch)

        if patch is None:
            agent_run.errors.append("Patch generation returned None")
            logger.debug("No patch for opportunity at %s", opp.location)
            continue

        agent_run.errors.append(None)

        # Convert AgentPatch → PatchResult for the existing validator
        proxy_patch = PatchResult(
            diff=patch.diff,
            explanation=patch.explanation,
            touched_files=patch.touched_files,
            template_name="llm_agent",
            lines_changed=patch.estimated_lines_changed,
        )

        # Validate (synchronous — Phase 9 pipeline)
        try:
            candidate_result = run_candidate_validation(
                repo_dir=repo_dir,
                config=detection,
                patch=proxy_patch,
                baseline=baseline,
            )
        except Exception as exc:
            logger.error("Validation raised for %s: %s", opp.location, exc)
            candidate_result = _make_error_candidate(str(exc))

        result.candidate_results.append(candidate_result)
        result.opportunity_for_candidate.append(opp)
        candidates_attempted += 1

        logger.info(
            "Candidate %d/%d at %s: accepted=%s",
            candidates_attempted, max_candidates,
            opp.location, candidate_result.is_accepted,
        )

    logger.info(
        "Agent cycle complete: %d attempted, %d accepted",
        result.total_attempted, result.accepted_count,
    )
    return result


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
