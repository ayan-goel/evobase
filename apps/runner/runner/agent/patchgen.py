"""LLM patch generation agent.

Given an `AgentOpportunity` and the repo directory, asks the LLM to
generate a unified diff that implements the fix. The diff is then
validated and constraint-checked using the existing `constraints.py`
module before being returned.

The agent includes a self-healing fallback: if the first diff is rejected
by the constraint checker, the agent is called a second time with the
constraint violation details appended so it can correct itself.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from runner.agent.types import AgentOpportunity, AgentPatch
from runner.llm.prompts.patch_prompts import patch_generation_prompt
from runner.llm.prompts.system_prompts import build_system_prompt
from runner.llm.provider import LLMProvider, LLMProviderError
from runner.llm.types import LLMConfig, LLMMessage, ThinkingTrace
from runner.patchgen.constraints import enforce_constraints
from runner.patchgen.types import ConstraintViolation, PatchResult

logger = logging.getLogger(__name__)

# Max characters of file content to send in a single patch generation call
MAX_FILE_CHARS = 32_000

# Maximum self-correction attempts when a constraint is violated
MAX_SELF_CORRECTION_ATTEMPTS = 1


async def generate_agent_patch(
    opportunity: AgentOpportunity,
    repo_dir: Path,
    provider: LLMProvider,
    config: LLMConfig,
    approach_override: Optional[str] = None,
) -> Optional[AgentPatch]:
    """Generate a patch for an `AgentOpportunity` using the LLM.

    Args:
        opportunity: The opportunity to fix.
        repo_dir: Absolute path to the checked-out repository.
        provider: Instantiated LLM provider.
        config: LLM configuration.
        approach_override: When set, replaces `opportunity.approach` in the
            patch prompt. Used by the multi-approach loop to try different
            implementation strategies for the same opportunity.

    Returns:
        An `AgentPatch` if the LLM produced a valid, constraint-compliant
        diff, or None if no valid patch could be generated.
    """
    repo_dir = Path(repo_dir)

    # Parse the file path from the location string ("file.ts:42" -> "file.ts")
    file_rel_path = _parse_file_from_location(opportunity.location)
    if not file_rel_path:
        logger.warning("Cannot parse file from opportunity location: %s", opportunity.location)
        return None

    file_path = repo_dir / file_rel_path
    if not file_path.is_file():
        logger.warning("Opportunity file not found: %s", file_path)
        return None

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.error("Cannot read %s: %s", file_path, exc)
        return None

    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS] + "\n\n... [file truncated at 32KB] ..."

    # Resolve which approach description to use for this attempt
    effective_approach = approach_override if approach_override is not None else opportunity.approach

    # Attempt patch generation (with self-correction on constraint violation)
    for attempt in range(1 + MAX_SELF_CORRECTION_ATTEMPTS):
        patch = await _call_patch_agent(
            file_rel_path=file_rel_path,
            content=content,
            opportunity=opportunity,
            approach=effective_approach,
            provider=provider,
            config=config,
        )
        if patch is None:
            return None

        # Validate constraints using the existing constraint checker
        try:
            proxy_result = PatchResult(
                diff=patch.diff,
                explanation=patch.explanation,
                touched_files=patch.touched_files,
                template_name="llm_agent",
                lines_changed=patch.estimated_lines_changed,
            )
            enforce_constraints(proxy_result)
            return patch  # Constraints passed

        except ConstraintViolation as exc:
            if attempt < MAX_SELF_CORRECTION_ATTEMPTS:
                logger.info(
                    "Patch constraint violation on attempt %d, retrying: %s",
                    attempt + 1, exc,
                )
                effective_approach = (
                    f"{effective_approach}\n\n"
                    f"PREVIOUS ATTEMPT FAILED constraint check: {exc}. "
                    "Produce a smaller, more focused diff that stays within limits."
                )
            else:
                logger.warning("Patch rejected after %d attempts: %s", attempt + 1, exc)
                return None

    return None


async def _call_patch_agent(
    file_rel_path: str,
    content: str,
    opportunity: AgentOpportunity,
    approach: str,
    provider: LLMProvider,
    config: LLMConfig,
) -> Optional[AgentPatch]:
    """Make one patch generation LLM call and parse the result."""
    from runner.detector.types import DetectionResult
    system_prompt = build_system_prompt(DetectionResult())  # Generic for patch gen

    prompt = patch_generation_prompt(
        file_path=file_rel_path,
        content=content,
        opportunity_type=opportunity.type,
        rationale=opportunity.rationale,
        approach=approach,
        risk_level=opportunity.risk_level,
    )

    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=prompt),
    ]

    try:
        response = await provider.complete(messages, config)
    except LLMProviderError as exc:
        logger.error("Patch generation LLM call failed: %s", exc)
        return None

    return _parse_patch_response(response.content, response.thinking_trace)


def _parse_patch_response(
    raw: str,
    thinking_trace: Optional[ThinkingTrace],
) -> Optional[AgentPatch]:
    """Parse the patch generation JSON response into an AgentPatch."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse patch response JSON: %s (raw: %r)", exc, raw[:200])
        return None

    diff = data.get("diff")
    if not diff:
        logger.debug("LLM returned null diff — no patch for this opportunity")
        return None

    explanation = str(data.get("explanation") or "")
    touched_files = data.get("touched_files", [])
    if not isinstance(touched_files, list):
        touched_files = []

    estimated = int(data.get("estimated_lines_changed", 0) or 0)

    if not diff.strip():
        return None

    return AgentPatch(
        diff=str(diff),
        explanation=explanation,
        touched_files=[str(f) for f in touched_files],
        estimated_lines_changed=estimated,
        thinking_trace=thinking_trace,
    )


def _parse_file_from_location(location: str) -> str:
    """Extract file path from a location string like 'src/utils.ts:42'."""
    if ":" not in location:
        return location
    return location.rsplit(":", 1)[0]
