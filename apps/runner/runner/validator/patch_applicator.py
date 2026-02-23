"""Apply and revert unified diffs against a repository directory.

Uses the system `patch` binary (available on all Unix/Linux/macOS systems)
so complex edge cases like context mismatches, binary files, and line endings
are handled correctly.

The diff string must be a unified diff as produced by difflib.unified_diff
(header lines like '--- a/file.ts' and '+++ b/file.ts', with -p1 strip level).
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# patch exit codes
_EXIT_SUCCESS = 0


class PatchApplyError(Exception):
    """Raised when a patch cannot be applied or reverted."""

    def __init__(self, message: str, stdout: str = "", stderr: str = ""):
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(message)


def apply_diff(repo_dir: Path, diff: str) -> None:
    """Apply a unified diff to files in repo_dir.

    Uses `patch -p1` to strip the leading 'a/' or 'b/' path prefix.
    Raises PatchApplyError if the patch cannot be cleanly applied.
    """
    if not diff.strip():
        raise PatchApplyError("Empty diff — nothing to apply")

    result = _run_patch(repo_dir, diff, reverse=False)

    if result.returncode != _EXIT_SUCCESS:
        raise PatchApplyError(
            f"patch failed with exit code {result.returncode}",
            stdout=result.stdout,
            stderr=result.stderr,
        )

    logger.debug("Patch applied successfully to %s", repo_dir)


def revert_diff(repo_dir: Path, diff: str) -> None:
    """Reverse a unified diff (undo a previously applied patch).

    Uses `patch -p1 -R` to apply the inverse transformation.
    Raises PatchApplyError if the revert fails.
    """
    if not diff.strip():
        raise PatchApplyError("Empty diff — nothing to revert")

    result = _run_patch(repo_dir, diff, reverse=True)

    if result.returncode != _EXIT_SUCCESS:
        raise PatchApplyError(
            f"patch revert failed with exit code {result.returncode}",
            stdout=result.stdout,
            stderr=result.stderr,
        )

    logger.debug("Patch reverted successfully in %s", repo_dir)


def _run_patch(
    repo_dir: Path,
    diff: str,
    reverse: bool,
) -> subprocess.CompletedProcess:
    """Run the patch command with appropriate flags.

    -p1       : strip the 'a/' / 'b/' prefix from diff paths
    -f        : force mode (no interactive prompts)
    -s        : silent (suppress "patching file" messages)
    --fuzz=3  : allow up to 3 context lines of mismatch when locating hunks;
                LLM-generated diffs sometimes have slightly off context even
                when the file content was provided verbatim in the prompt.
    -R        : reverse (applied only when reverting)
    """
    cmd = ["patch", "-p1", "-f", "-s", "--fuzz=3"]
    if reverse:
        cmd.append("-R")

    try:
        return subprocess.run(
            cmd,
            input=diff,
            text=True,
            capture_output=True,
            cwd=str(repo_dir),
        )
    except FileNotFoundError:
        raise PatchApplyError(
            "patch binary not found; ensure `patch` is installed on the system"
        )
    except Exception as exc:
        raise PatchApplyError(f"Unexpected error running patch: {exc}")


def check_patch_available() -> bool:
    """Return True if the system `patch` binary is accessible."""
    try:
        result = subprocess.run(
            ["patch", "--version"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
