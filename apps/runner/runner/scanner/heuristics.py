"""Heuristic-based opportunity scanner.

Uses regex pattern matching to detect common optimization opportunities
in JavaScript and TypeScript files. Faster than AST parsing and catches
patterns that are straightforward to detect textually.

Each heuristic function returns a list of Opportunities.
"""

import logging
import re
from pathlib import Path

from runner.scanner.types import Opportunity

logger = logging.getLogger(__name__)


def scan_heuristics(file_path: Path, content: str) -> list[Opportunity]:
    """Run all heuristic checks on a single file.

    Returns opportunities found, with location set to file:line.
    """
    opportunities: list[Opportunity] = []
    rel_path = str(file_path)
    lines = content.splitlines()

    for line_num, line in enumerate(lines, start=1):
        location = f"{rel_path}:{line_num}"

        opp = _check_indexof_membership(line, location)
        if opp:
            opportunities.append(opp)

        opp = _check_json_parse_pattern(line, location)
        if opp:
            opportunities.append(opp)

        opp = _check_string_concat_in_loop(line, line_num, lines, location)
        if opp:
            opportunities.append(opp)

        opp = _check_sync_fs(line, location)
        if opp:
            opportunities.append(opp)

        opp = _check_regex_in_loop(line, line_num, lines, location)
        if opp:
            opportunities.append(opp)

    return opportunities


# Pattern: arr.indexOf(x) !== -1 or arr.indexOf(x) >= 0
_INDEXOF_PATTERN = re.compile(
    r"\.indexOf\s*\([^)]+\)\s*(!==\s*-1|>=\s*0|>\s*-1|===\s*-1|<\s*0)"
)


def _check_indexof_membership(line: str, location: str) -> Opportunity | None:
    """Detect Array.indexOf used for membership checks.

    These can be replaced with Set.has() for O(1) lookup when the
    array is accessed multiple times.
    """
    if _INDEXOF_PATTERN.search(line):
        return Opportunity(
            type="set_membership",
            location=location,
            rationale="Array.indexOf used for membership check; consider Set.has() for O(1) lookup",
            risk_score=0.2,
            source="heuristic",
        )
    return None


# Pattern: JSON.parse( used multiple times (detected per-line, aggregated by orchestrator)
_JSON_PARSE_PATTERN = re.compile(r"JSON\.parse\s*\(")


def _check_json_parse_pattern(line: str, location: str) -> Opportunity | None:
    """Detect JSON.parse calls that may be redundant.

    Repeated JSON.parse on the same string is wasteful.
    The AST scanner provides more precise analysis; this is a coarse signal.
    """
    if _JSON_PARSE_PATTERN.search(line):
        return Opportunity(
            type="json_parse_cache",
            location=location,
            rationale="JSON.parse call detected; if called repeatedly on the same string, cache the result",
            risk_score=0.3,
            source="heuristic",
        )
    return None


def _check_string_concat_in_loop(
    line: str, line_num: int, lines: list[str], location: str
) -> Opportunity | None:
    """Detect string concatenation inside loops.

    Pattern: += inside a for/while/do block with a string operand.
    """
    stripped = line.strip()
    if "+=" not in stripped:
        return None

    # Check if we're inside a loop by scanning preceding lines for loop keywords
    if _is_inside_loop(line_num, lines):
        return Opportunity(
            type="string_concat_loop",
            location=location,
            rationale="String concatenation (+=) inside a loop; consider Array.join() for better performance",
            risk_score=0.3,
            source="heuristic",
        )
    return None


# Pattern: synchronous fs methods
_SYNC_FS_PATTERN = re.compile(
    r"\bfs\.(readFileSync|writeFileSync|existsSync|mkdirSync|readdirSync|statSync|unlinkSync)\b"
)


def _check_sync_fs(line: str, location: str) -> Opportunity | None:
    """Detect synchronous fs calls that block the event loop."""
    if _SYNC_FS_PATTERN.search(line):
        return Opportunity(
            type="sync_fs_in_handler",
            location=location,
            rationale="Synchronous fs call detected; use async alternative to avoid blocking the event loop",
            risk_score=0.4,
            source="heuristic",
        )
    return None


_REGEX_LITERAL = re.compile(r"new\s+RegExp\s*\(|/[^/]+/[gimsuy]*")


def _check_regex_in_loop(
    line: str, line_num: int, lines: list[str], location: str
) -> Opportunity | None:
    """Detect regex compilation inside loops.

    Creating RegExp objects or using regex literals inside loops
    causes unnecessary recompilation.
    """
    if not _REGEX_LITERAL.search(line):
        return None

    if _is_inside_loop(line_num, lines):
        return Opportunity(
            type="regex_in_loop",
            location=location,
            rationale="Regex compiled inside a loop; hoist to a constant outside the loop",
            risk_score=0.2,
            source="heuristic",
        )
    return None


def _is_inside_loop(line_num: int, lines: list[str], lookback: int = 10) -> bool:
    """Check if a line is likely inside a loop by scanning preceding lines.

    Simple heuristic: looks for for/while/do keywords with opening braces
    in the preceding lines without matching closing braces.
    """
    start = max(0, line_num - lookback - 1)
    preceding = lines[start:line_num - 1]

    brace_depth = 0
    in_loop = False

    for prev_line in preceding:
        stripped = prev_line.strip()

        if re.match(r"^(for|while|do)\b", stripped):
            in_loop = True

        brace_depth += stripped.count("{") - stripped.count("}")

    return in_loop and brace_depth > 0
