"""LLM discovery agent — finds optimisation opportunities in a repository.

Two-stage process:
  Stage 1: The agent receives the repo map and selects which files to
           analyse in detail. This keeps the context window manageable.

  Stage 2: For each selected file, the agent reads the full content and
           produces a structured list of `AgentOpportunity` objects,
           each with a reasoning trace.

Design decisions:
  - File reads are done sequentially (not in parallel) to avoid sending
    too many large files in simultaneous API calls.
  - A maximum of MAX_FILES_TO_ANALYSE files are processed per cycle to
    bound cost and latency.
  - Malformed JSON from the LLM is logged and skipped gracefully; partial
    results are still returned so the run doesn't fail completely.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from runner.agent.repo_map import build_repo_map
from runner.agent.types import AgentOpportunity
from runner.detector.types import DetectionResult
from runner.llm.prompts.discovery_prompts import analysis_prompt, file_selection_prompt
from runner.llm.prompts.system_prompts import build_system_prompt
from runner.llm.provider import LLMProvider, LLMProviderError
from runner.llm.types import LLMConfig, LLMMessage, ThinkingTrace

logger = logging.getLogger(__name__)

# Hard cap on files analysed per run to bound API cost
MAX_FILES_TO_ANALYSE = 10

# Hard cap on opportunities to return (stops the patch queue exploding)
MAX_OPPORTUNITIES = 30

# Maximum file size to send to the LLM (32KB) — larger files are truncated
MAX_FILE_CHARS = 32_000


async def discover_opportunities(
    repo_dir: Path,
    detection: DetectionResult,
    provider: LLMProvider,
    config: LLMConfig,
    seen_signatures: frozenset[tuple[str, str]] = frozenset(),
) -> list[AgentOpportunity]:
    """Run the two-stage discovery pipeline and return all opportunities.

    Args:
        repo_dir: Absolute path to the checked-out repository.
        detection: Output from the detector (framework, commands, etc.).
        provider: Instantiated LLM provider to use for API calls.
        config: LLM configuration (model, API key, etc.).
        seen_signatures: Set of (type, file_path) pairs already recorded for
            this repository across all previous runs. Opportunities whose
            (type, file_path) match an entry are filtered out before returning
            so the same suggestion is never re-proposed.

    Returns:
        List of `AgentOpportunity` objects sorted by risk score ascending
        (safest first). Includes the thinking trace for each opportunity.
    """
    repo_dir = Path(repo_dir)
    system_prompt = build_system_prompt(detection)

    # Stage 1: file selection
    selected_files = await _select_files(repo_dir, system_prompt, provider, config)
    if not selected_files:
        logger.warning("LLM returned no files to analyse; skipping discovery")
        return []

    logger.info("Discovery: selected %d files for analysis", len(selected_files))

    # Stage 2: per-file analysis
    all_opportunities: list[AgentOpportunity] = []

    for rel_path in selected_files[:MAX_FILES_TO_ANALYSE]:
        file_path = repo_dir / rel_path
        if not file_path.is_file():
            logger.warning("Selected file not found: %s", rel_path)
            continue

        opps = await _analyse_file(rel_path, file_path, system_prompt, provider, config)
        all_opportunities.extend(opps)

    # Deduplicate by location (same location from multiple passes = keep first)
    seen_locations: set[str] = set()
    deduped: list[AgentOpportunity] = []
    for opp in all_opportunities:
        if opp.location not in seen_locations:
            seen_locations.add(opp.location)
            deduped.append(opp)

    # Filter out opportunities the agent has already proposed in previous runs
    if seen_signatures:
        before = len(deduped)
        deduped = [o for o in deduped if _is_new(o, seen_signatures)]
        filtered = before - len(deduped)
        if filtered:
            logger.debug(
                "Deduplication: skipped %d already-seen opportunity(s)", filtered
            )

    # Sort by risk score (safest first) then cap
    deduped.sort(key=lambda o: o.risk_score)
    result = deduped[:MAX_OPPORTUNITIES]

    logger.info(
        "Discovery complete: %d opportunities found across %d files",
        len(result), len(selected_files),
    )
    return result


def _is_new(opp: AgentOpportunity, seen: frozenset[tuple[str, str]]) -> bool:
    """Return True if this opportunity has not been seen in a previous run."""
    file_path = opp.location.split(":")[0].strip() if opp.location else ""
    return (opp.type, file_path) not in seen


async def _select_files(
    repo_dir: Path,
    system_prompt: str,
    provider: LLMProvider,
    config: LLMConfig,
) -> list[str]:
    """Stage 1: ask the LLM to pick which files to analyse."""
    repo_map = build_repo_map(repo_dir)
    prompt = file_selection_prompt(repo_map)

    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=prompt),
    ]

    try:
        response = await provider.complete(messages, config)
    except LLMProviderError as exc:
        logger.error("File selection LLM call failed: %s", exc)
        return []

    logger.info(
        "File selection LLM response length=%d, first 300 chars: %r",
        len(response.content or ""),
        (response.content or "")[:300],
    )
    result = _parse_file_list(response.content)
    logger.info("Parsed %d files from selection response", len(result))
    return result


async def _analyse_file(
    rel_path: str,
    file_path: Path,
    system_prompt: str,
    provider: LLMProvider,
    config: LLMConfig,
) -> list[AgentOpportunity]:
    """Stage 2: analyse a single file for opportunities."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", file_path, exc)
        return []

    # Truncate very large files with a clear marker
    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS] + "\n\n... [file truncated at 32KB] ..."

    prompt = analysis_prompt(rel_path, content)
    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=prompt),
    ]

    try:
        response = await provider.complete(messages, config)
    except LLMProviderError as exc:
        logger.error("Analysis LLM call failed for %s: %s", rel_path, exc)
        return []

    opps = _parse_opportunities(response.content, response.thinking_trace)
    logger.info(
        "Analysis of %s: found %d opportunities (response length=%d)",
        rel_path, len(opps), len(response.content or ""),
    )
    return opps


def _strip_markdown_fences(raw: str) -> str:
    """Strip markdown code fences (```json ... ```) from LLM output."""
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _parse_file_list(raw: str) -> list[str]:
    """Parse the file selection JSON response into a list of paths."""
    if not raw:
        return []
    cleaned = _strip_markdown_fences(raw)
    try:
        data = json.loads(cleaned)
        files = data.get("files", [])
        if isinstance(files, list):
            return [str(f) for f in files if f]
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Could not parse file selection response: %r", raw[:200])
    return []


def _parse_opportunities(
    raw: str,
    thinking_trace: Optional[ThinkingTrace],
) -> list[AgentOpportunity]:
    """Parse the analysis JSON response into AgentOpportunity objects."""
    if not raw:
        return []
    cleaned = _strip_markdown_fences(raw)
    try:
        data = json.loads(cleaned)
        raw_opps = data.get("opportunities", [])
        if not isinstance(raw_opps, list):
            return []

        result = []
        for item in raw_opps:
            if not isinstance(item, dict):
                continue
            # Support both new `approaches` list and legacy `approach` string
            approaches_raw = item.get("approaches")
            if isinstance(approaches_raw, list):
                approaches = [str(a) for a in approaches_raw if a]
            else:
                # Fall back to legacy single-string field
                legacy = item.get("approach", "")
                approaches = [str(legacy)] if legacy else []
            opp = AgentOpportunity(
                type=str(item.get("type", "performance")),
                location=str(item.get("location", "")),
                rationale=str(item.get("rationale", "")),
                risk_level=str(item.get("risk_level", "medium")),
                approaches=approaches,
                affected_lines=int(item.get("affected_lines", 0)),
                thinking_trace=thinking_trace,
            )
            if opp.location:  # Skip opportunities without a location
                result.append(opp)
        return result

    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Could not parse opportunity response: %s (raw: %r)", exc, raw[:200])
    return []
