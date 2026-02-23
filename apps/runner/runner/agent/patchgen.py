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
from dataclasses import dataclass, field
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


PATCHGEN_FAILURE_STAGE_LLM_CALL = "llm_call"
PATCHGEN_FAILURE_STAGE_JSON_PARSE = "json_parse"
PATCHGEN_FAILURE_STAGE_NULL_DIFF = "null_diff"
PATCHGEN_FAILURE_STAGE_CONSTRAINT = "constraint"
PATCHGEN_FAILURE_STAGE_FILE_MISSING = "file_missing"
PATCHGEN_FAILURE_STAGE_FILE_READ = "file_read"
PATCHGEN_FAILURE_STAGE_UNKNOWN = "unknown"


@dataclass
class PatchGenTryRecord:
    attempt_number: int
    success: bool
    failure_stage: Optional[str] = None
    failure_reason: Optional[str] = None
    patch: Optional[AgentPatch] = None
    patch_trace: Optional[ThinkingTrace] = None


@dataclass
class PatchGenerationOutcome:
    success: bool
    patch: Optional[AgentPatch]
    failure_stage: Optional[str] = None
    failure_reason: Optional[str] = None
    tries: list[PatchGenTryRecord] = field(default_factory=list)


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
    outcome = await generate_agent_patch_with_diagnostics(
        opportunity=opportunity,
        repo_dir=repo_dir,
        provider=provider,
        config=config,
        approach_override=approach_override,
    )
    return outcome.patch


async def generate_agent_patch_with_diagnostics(
    opportunity: AgentOpportunity,
    repo_dir: Path,
    provider: LLMProvider,
    config: LLMConfig,
    approach_override: Optional[str] = None,
) -> PatchGenerationOutcome:
    """Generate a patch and return detailed diagnostics for live event streaming."""
    repo_dir = Path(repo_dir)

    file_rel_path = _parse_file_from_location(opportunity.location)
    if not file_rel_path:
        logger.warning("Cannot parse file from opportunity location: %s", opportunity.location)
        return PatchGenerationOutcome(
            success=False,
            patch=None,
            failure_stage=PATCHGEN_FAILURE_STAGE_UNKNOWN,
            failure_reason=f"Cannot parse file from opportunity location: {opportunity.location}",
            tries=[],
        )

    file_path = repo_dir / file_rel_path
    if not file_path.is_file():
        logger.warning("Opportunity file not found: %s", file_path)
        return PatchGenerationOutcome(
            success=False,
            patch=None,
            failure_stage=PATCHGEN_FAILURE_STAGE_FILE_MISSING,
            failure_reason=f"Opportunity file not found: {file_path}",
            tries=[],
        )

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.error("Cannot read %s: %s", file_path, exc)
        return PatchGenerationOutcome(
            success=False,
            patch=None,
            failure_stage=PATCHGEN_FAILURE_STAGE_FILE_READ,
            failure_reason=str(exc),
            tries=[],
        )

    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS] + "\n\n... [file truncated at 32KB] ..."

    effective_approach = approach_override if approach_override is not None else opportunity.approach
    tries: list[PatchGenTryRecord] = []

    for attempt in range(1 + MAX_SELF_CORRECTION_ATTEMPTS):
        try_record = await _call_patch_agent_with_diagnostics(
            attempt_number=attempt + 1,
            file_rel_path=file_rel_path,
            content=content,
            opportunity=opportunity,
            approach=effective_approach,
            provider=provider,
            config=config,
        )
        tries.append(try_record)

        if not try_record.success or try_record.patch is None:
            return PatchGenerationOutcome(
                success=False,
                patch=None,
                failure_stage=try_record.failure_stage,
                failure_reason=try_record.failure_reason,
                tries=tries,
            )

        patch = try_record.patch
        try:
            proxy_result = PatchResult(
                diff=patch.diff,
                explanation=patch.explanation,
                touched_files=patch.touched_files,
                template_name="llm_agent",
                lines_changed=patch.estimated_lines_changed,
            )
            enforce_constraints(proxy_result)
            return PatchGenerationOutcome(
                success=True,
                patch=patch,
                failure_stage=None,
                failure_reason=None,
                tries=tries,
            )
        except ConstraintViolation as exc:
            try_record.success = False
            try_record.failure_stage = PATCHGEN_FAILURE_STAGE_CONSTRAINT
            try_record.failure_reason = str(exc)
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
                continue

            logger.warning("Patch rejected after %d attempts: %s", attempt + 1, exc)
            return PatchGenerationOutcome(
                success=False,
                patch=None,
                failure_stage=PATCHGEN_FAILURE_STAGE_CONSTRAINT,
                failure_reason=str(exc),
                tries=tries,
            )

    return PatchGenerationOutcome(
        success=False,
        patch=None,
        failure_stage=PATCHGEN_FAILURE_STAGE_UNKNOWN,
        failure_reason="Patch generation failed without a recorded outcome",
        tries=tries,
    )


async def _call_patch_agent(
    file_rel_path: str,
    content: str,
    opportunity: AgentOpportunity,
    approach: str,
    provider: LLMProvider,
    config: LLMConfig,
) -> Optional[AgentPatch]:
    """Make one patch generation LLM call and parse the result."""
    try_record = await _call_patch_agent_with_diagnostics(
        attempt_number=1,
        file_rel_path=file_rel_path,
        content=content,
        opportunity=opportunity,
        approach=approach,
        provider=provider,
        config=config,
    )
    return try_record.patch


async def _call_patch_agent_with_diagnostics(
    attempt_number: int,
    file_rel_path: str,
    content: str,
    opportunity: AgentOpportunity,
    approach: str,
    provider: LLMProvider,
    config: LLMConfig,
) -> PatchGenTryRecord:
    """Make one patch generation LLM call and capture parse diagnostics."""
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
        return PatchGenTryRecord(
            attempt_number=attempt_number,
            success=False,
            failure_stage=PATCHGEN_FAILURE_STAGE_LLM_CALL,
            failure_reason=str(exc),
            patch=None,
            patch_trace=None,
        )

    patch, failure_stage, failure_reason = _parse_patch_response_detailed(
        response.content,
        response.thinking_trace,
    )
    return PatchGenTryRecord(
        attempt_number=attempt_number,
        success=patch is not None,
        failure_stage=failure_stage,
        failure_reason=failure_reason,
        patch=patch,
        patch_trace=patch.thinking_trace if patch else response.thinking_trace,
    )


def _parse_patch_response(
    raw: str,
    thinking_trace: Optional[ThinkingTrace],
) -> Optional[AgentPatch]:
    """Parse the patch generation JSON response into an AgentPatch."""
    patch, _failure_stage, _failure_reason = _parse_patch_response_detailed(raw, thinking_trace)
    return patch


def _parse_patch_response_detailed(
    raw: str,
    thinking_trace: Optional[ThinkingTrace],
) -> tuple[Optional[AgentPatch], Optional[str], Optional[str]]:
    """Parse the patch response and return (patch, failure_stage, failure_reason)."""
    if not raw:
        return None, PATCHGEN_FAILURE_STAGE_NULL_DIFF, "empty response"
    cleaned = _strip_markdown_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse patch response JSON: %s (raw: %r)", exc, raw[:200])
        return None, PATCHGEN_FAILURE_STAGE_JSON_PARSE, str(exc)

    diff = data.get("diff")
    if not diff:
        logger.debug("LLM returned null diff — no patch for this opportunity")
        return None, PATCHGEN_FAILURE_STAGE_NULL_DIFF, "LLM returned null diff"

    explanation = str(data.get("explanation") or "")
    touched_files = data.get("touched_files", [])
    if not isinstance(touched_files, list):
        touched_files = []

    estimated = int(data.get("estimated_lines_changed", 0) or 0)

    if not diff.strip():
        return None, PATCHGEN_FAILURE_STAGE_NULL_DIFF, "LLM returned empty diff"

    return AgentPatch(
        diff=str(diff),
        explanation=explanation,
        touched_files=[str(f) for f in touched_files],
        estimated_lines_changed=estimated,
        thinking_trace=thinking_trace,
    ), None, None


def _parse_file_from_location(location: str) -> str:
    """Extract file path from a location string like 'src/utils.ts:42'."""
    if ":" not in location:
        return location
    return location.rsplit(":", 1)[0]


def _strip_markdown_fences(raw: str) -> str:
    """Strip a surrounding Markdown code fence (```json ... ```) if present."""
    text = raw.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if not lines:
        return text
    if not lines[0].startswith("```"):
        return text

    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()

    return text
