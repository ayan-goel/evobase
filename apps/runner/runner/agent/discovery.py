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
from typing import Callable, Optional

from runner.agent.repo_map import build_repo_map
from runner.agent.types import AgentOpportunity
from runner.detector.types import DetectionResult
from runner.llm.prompts.discovery_prompts import analysis_prompt, file_selection_prompt
from runner.llm.prompts.system_prompts import build_system_prompt
from runner.llm.provider import LLMProvider, LLMProviderError
from runner.llm.types import LLMConfig, LLMMessage, ThinkingTrace, get_selection_model

logger = logging.getLogger(__name__)

# Hard cap on files analysed per run to bound API cost
MAX_FILES_TO_ANALYSE = 10

# Maximum file size to send to the LLM (20KB) — larger files are truncated
MAX_FILE_CHARS = 20_000


def _selection_config(config: LLMConfig) -> LLMConfig:
    """Return a cost-optimised config for the file-selection stage.

    File selection is a simple ranking task — disable thinking and
    switch to the provider's cheap/fast model.
    """
    from dataclasses import replace
    selection_model = get_selection_model(config.provider, config.model)
    return replace(
        config,
        model=selection_model,
        enable_thinking=False,
        thinking_budget_tokens=0,
        reasoning_effort="low",
    )


def _analysis_config(config: LLMConfig) -> LLMConfig:
    """Return a config for the file-analysis stage.

    Uses a reduced thinking budget relative to patch generation.
    """
    from dataclasses import replace
    return replace(
        config,
        thinking_budget_tokens=3000,
        reasoning_effort="medium",
    )


EventCallback = Callable[[str, str, dict], None]


async def discover_opportunities(
    repo_dir: Path,
    detection: DetectionResult,
    provider: LLMProvider,
    config: LLMConfig,
    seen_signatures: frozenset[tuple[str, str]] = frozenset(),
    on_event: Optional[EventCallback] = None,
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
        on_event: Optional callback invoked as on_event(event_type, phase, data)
            for each significant discovery step. Used for real-time streaming.

    Returns:
        List of `AgentOpportunity` objects sorted by risk score ascending
        (safest first). Includes the thinking trace for each opportunity.
    """
    def _emit(event_type: str, data: dict) -> None:
        if on_event:
            try:
                on_event(event_type, "discovery", data)
            except Exception:
                pass

    repo_dir = Path(repo_dir)
    system_prompt = build_system_prompt(detection)

    # Stage 1: file selection (seen_signatures inform the LLM to explore new files)
    selected_files = await _select_files(
        repo_dir, system_prompt, provider, config, seen_signatures=seen_signatures,
    )
    if not selected_files:
        logger.warning("LLM returned no files to analyse; skipping discovery")
        return []

    logger.info("Discovery: selected %d files for analysis", len(selected_files))
    _emit("discovery.files.selected", {
        "count": len(selected_files),
        "files": selected_files,
    })

    # Stage 2: per-file analysis
    all_opportunities: list[AgentOpportunity] = []
    capped_files = selected_files[:MAX_FILES_TO_ANALYSE]

    for file_index, rel_path in enumerate(capped_files):
        file_path = repo_dir / rel_path
        if not file_path.is_file():
            logger.warning("Selected file not found: %s", rel_path)
            continue

        _emit("discovery.file.analysing", {
            "file": rel_path,
            "file_index": file_index,
            "total_files": len(capped_files),
        })
        opps = await _analyse_file(
            rel_path, file_path, system_prompt, provider, config,
            seen_signatures=seen_signatures,
        )
        _emit("discovery.file.analysed", {
            "file": rel_path,
            "file_index": file_index,
            "total_files": len(capped_files),
            "opportunities_found": len(opps),
            "opportunities": _serialise_file_opportunities_for_event(rel_path, opps),
        })
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

    # Sort by risk score (safest first)
    deduped.sort(key=lambda o: o.risk_score)

    logger.info(
        "Discovery complete: %d opportunities found across %d files",
        len(deduped), len(selected_files),
    )
    return deduped


def _serialise_file_opportunities_for_event(
    rel_path: str,
    opps: list[AgentOpportunity],
) -> list[dict]:
    """Serialise discovery-stage opportunities for a file into a compact event payload."""
    return [
        {
            "file": rel_path,
            "location": opp.location,
            "type": opp.type,
            "rationale": opp.rationale,
            "risk_level": opp.risk_level,
            "affected_lines": opp.affected_lines,
            "approaches": [str(a) for a in opp.approaches if a],
        }
        for opp in opps
    ]


def _is_new(opp: AgentOpportunity, seen: frozenset[tuple[str, str]]) -> bool:
    """Return True if this opportunity has not been seen in a previous run."""
    file_path = opp.location.split(":")[0].strip() if opp.location else ""
    return (opp.type, file_path) not in seen


def _format_seen_for_file_selection(
    seen_signatures: frozenset[tuple[str, str]],
) -> str:
    """Format the full set of seen signatures as a bulleted list for the
    file-selection prompt so the LLM can deprioritise already-explored files."""
    if not seen_signatures:
        return ""
    lines = sorted(f"- [{sig_type}] {sig_file}" for sig_type, sig_file in seen_signatures)
    return "\n".join(lines)


def _format_seen_for_file(
    file_path: str,
    seen_signatures: frozenset[tuple[str, str]],
) -> str:
    """Format seen signatures for a specific file as a bulleted list for the
    per-file analysis prompt."""
    relevant = sorted(
        f"- {sig_type}"
        for sig_type, sig_file in seen_signatures
        if sig_file == file_path
    )
    return "\n".join(relevant) if relevant else ""


async def _select_files(
    repo_dir: Path,
    system_prompt: str,
    provider: LLMProvider,
    config: LLMConfig,
    seen_signatures: frozenset[tuple[str, str]] = frozenset(),
) -> list[str]:
    """Stage 1: ask the LLM to pick which files to analyse."""
    repo_map = build_repo_map(repo_dir)
    previously_found = _format_seen_for_file_selection(seen_signatures)
    prompt = file_selection_prompt(repo_map, previously_found=previously_found)

    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=prompt),
    ]

    try:
        response = await provider.complete(messages, _selection_config(config))
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
    seen_signatures: frozenset[tuple[str, str]] = frozenset(),
) -> list[AgentOpportunity]:
    """Stage 2: analyse a single file for opportunities."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", file_path, exc)
        return []

    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS] + "\n\n... [file truncated at 20KB] ..."

    already_found = _format_seen_for_file(rel_path, seen_signatures)
    prompt = analysis_prompt(rel_path, content, already_found_in_file=already_found)
    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=prompt),
    ]

    try:
        response = await provider.complete(messages, _analysis_config(config))
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


def _try_parse_json(text: str) -> dict | None:
    """Robustly parse JSON, handling common LLM quirks.

    Tries in order:
    1. Direct parse
    2. Strip trailing commas (common Gemini/GPT mistake)
    3. Extract outermost { ... } brace pair (ignore surrounding prose)
    """
    import re

    for candidate in (text, re.sub(r",\s*([}\]])", r"\1", text)):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass

    brace_start = text.find("{")
    if brace_start >= 0:
        depth = 0
        for i, ch in enumerate(text[brace_start:], start=brace_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    json_slice = text[brace_start:i + 1]
                    for candidate in (json_slice, re.sub(r",\s*([}\]])", r"\1", json_slice)):
                        try:
                            data = json.loads(candidate)
                            if isinstance(data, dict):
                                return data
                        except (json.JSONDecodeError, TypeError):
                            pass
                    break

    return None


def _parse_file_list(raw: str) -> list[str]:
    """Parse the file selection JSON response into a list of paths.

    Handles common LLM quirks: markdown fences, trailing prose after the JSON
    object, trailing commas, and embedded JSON in surrounding text.
    """
    if not raw:
        return []

    cleaned = _strip_markdown_fences(raw)
    data = _try_parse_json(cleaned)
    if data is not None:
        files = data.get("files", [])
        if isinstance(files, list):
            return [str(f) for f in files if f]

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
    data = _try_parse_json(cleaned)
    if data is None:
        logger.warning("Could not parse opportunity response (raw: %r)", raw[:200])
        return []

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
        if opp.location:
            result.append(opp)
    return result
