"""Patch generator orchestrator.

Selects the right template for a given opportunity, applies it
to the source file, computes the unified diff, enforces constraints,
and returns a PatchResult.
"""

import difflib
import logging
from pathlib import Path
from typing import Optional

from runner.patchgen.constraints import count_diff_lines, enforce_constraints
from runner.patchgen.templates import TEMPLATE_REGISTRY
from runner.patchgen.types import ConstraintViolation, PatchResult
from runner.scanner.types import Opportunity

logger = logging.getLogger(__name__)


def generate_patch(
    opportunity: Opportunity,
    repo_dir: Path,
) -> Optional[PatchResult]:
    """Generate a patch for an opportunity in a repository.

    Selects the appropriate template, applies it to the source file,
    computes the unified diff, and enforces all hard constraints.

    Returns None if:
    - No template exists for the opportunity type
    - The template cannot apply to the specific code pattern
    - A constraint violation would occur

    Raises ConstraintViolation if the generated patch violates limits.
    """
    template_cls = TEMPLATE_REGISTRY.get(opportunity.type)
    if not template_cls:
        logger.debug("No template for opportunity type: %s", opportunity.type)
        return None

    # Parse location: "src/utils.ts:42" -> file="src/utils.ts", line=42
    file_path, line_str = _parse_location(opportunity.location)
    if not file_path or not line_str:
        logger.warning("Cannot parse opportunity location: %s", opportunity.location)
        return None

    source_path = repo_dir / file_path
    if not source_path.exists():
        logger.warning("Source file not found: %s", source_path)
        return None

    try:
        original_source = source_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to read %s: %s", source_path, exc)
        return None

    template = template_cls()

    try:
        modified_source = template.apply(original_source, line_str)
    except Exception as exc:
        logger.error("Template %s failed: %s", template.name, exc)
        return None

    if modified_source is None:
        logger.debug(
            "Template %s could not apply to %s:%s",
            template.name, file_path, line_str,
        )
        return None

    if modified_source == original_source:
        logger.debug("Template %s produced no change", template.name)
        return None

    diff = _compute_diff(original_source, modified_source, file_path)
    lines_changed = count_diff_lines(diff)

    patch = PatchResult(
        diff=diff,
        explanation=template.explanation,
        touched_files=[file_path],
        template_name=template.name,
        lines_changed=lines_changed,
    )

    try:
        enforce_constraints(patch)
    except ConstraintViolation as exc:
        logger.warning("Patch violates constraint: %s", exc)
        raise

    return patch


def _parse_location(location: str) -> tuple[str, str]:
    """Split 'src/utils.ts:42' into ('src/utils.ts', '42')."""
    if ":" not in location:
        return "", ""
    # Split from the right to handle Windows paths like C:\path\file.ts:42
    parts = location.rsplit(":", 1)
    return parts[0], parts[1]


def _compute_diff(original: str, modified: str, file_path: str) -> str:
    """Compute a unified diff between original and modified source.

    Uses keepends=True so content lines carry their own newlines, and
    lineterm='\\n' so the --- / +++ / @@ header lines are also newline-
    terminated. This produces a well-formed unified diff that `patch -p1`
    accepts without complaints.
    """
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff_lines = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="\n",
    )
    return "".join(diff_lines)
