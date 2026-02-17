"""Hard constraint enforcement for patch generation.

Constraints are enforced before any patch is accepted:
  - ≤ 5 files touched
  - ≤ 200 lines changed (additions + deletions)
  - No config, test, or dependency files modified

These are safety rails to ensure patches are surgical and reversible.
"""

import re
from pathlib import Path

from runner.patchgen.types import ConstraintViolation, PatchResult

# Maximum number of files a single patch may touch
MAX_FILES = 5

# Maximum total line changes (additions + deletions)
MAX_LINES_CHANGED = 200

# Patterns that identify config/test/dependency files that must not be patched
_FORBIDDEN_PATTERNS = [
    # Package managers
    r"package\.json$",
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"pnpm-lock\.yaml$",
    r"bun\.lockb$",
    # Config files
    r"\.env",
    r"tsconfig.*\.json$",
    r"jest\.config\.",
    r"vitest\.config\.",
    r"eslint\.config\.",
    r"prettier\.config\.",
    r"babel\.config\.",
    r"webpack\.config\.",
    r"vite\.config\.",
    r"next\.config\.",
    r"tailwind\.config\.",
    r"postcss\.config\.",
    # Test files
    r"\.test\.[jt]sx?$",
    r"\.spec\.[jt]sx?$",
    r"__tests__/",
    r"(?:^|/)tests?/",
]

_FORBIDDEN_COMPILED = [re.compile(p) for p in _FORBIDDEN_PATTERNS]


def enforce_constraints(patch: PatchResult) -> None:
    """Enforce all hard constraints on a patch.

    Raises ConstraintViolation if any constraint is violated.
    This is always called before a patch is accepted.
    """
    _check_file_count(patch)
    _check_line_count(patch)
    _check_forbidden_files(patch)


def _check_file_count(patch: PatchResult) -> None:
    count = len(patch.touched_files)
    if count > MAX_FILES:
        raise ConstraintViolation(
            "max_files",
            f"Patch touches {count} files; maximum is {MAX_FILES}",
        )


def _check_line_count(patch: PatchResult) -> None:
    lines = count_diff_lines(patch.diff)
    if lines > MAX_LINES_CHANGED:
        raise ConstraintViolation(
            "max_lines",
            f"Patch changes {lines} lines; maximum is {MAX_LINES_CHANGED}",
        )


def _check_forbidden_files(patch: PatchResult) -> None:
    for file_path in patch.touched_files:
        normalized = file_path.replace("\\", "/")
        for pattern in _FORBIDDEN_COMPILED:
            if pattern.search(normalized):
                raise ConstraintViolation(
                    "forbidden_file",
                    f"Patch touches forbidden file '{file_path}' (matches pattern '{pattern.pattern}')",
                )


def count_diff_lines(diff: str) -> int:
    """Count total added + removed lines in a unified diff string.

    Only counts lines starting with '+' or '-' (not '+++' / '---' headers).
    """
    count = 0
    for line in diff.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            count += 1
    return count


def is_forbidden_file(file_path: str) -> bool:
    """Check if a file path matches any forbidden pattern."""
    normalized = file_path.replace("\\", "/")
    return any(p.search(normalized) for p in _FORBIDDEN_COMPILED)
