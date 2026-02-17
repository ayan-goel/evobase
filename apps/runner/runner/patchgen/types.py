"""Types for the patch generation module.

PatchResult is the single output type from any patch template.
It carries the unified diff, explanation, affected files list,
and metadata about how the patch was generated.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PatchResult:
    """A generated patch ready for validation and proposal creation.

    diff: Unified diff string (as produced by difflib).
    explanation: Human-readable description of what changed and why.
    touched_files: List of relative file paths modified by the patch.
    template_name: Which template generated this patch.
    lines_changed: Total added + removed lines (for constraint checks).
    """

    diff: str
    explanation: str
    touched_files: list[str]
    template_name: str
    lines_changed: int = 0

    def to_dict(self) -> dict:
        return {
            "diff": self.diff,
            "explanation": self.explanation,
            "touched_files": self.touched_files,
            "template_name": self.template_name,
            "lines_changed": self.lines_changed,
        }


class ConstraintViolation(Exception):
    """Raised when a patch violates hard generation constraints.

    Carries details about which constraint was violated and by how much.
    """

    def __init__(self, constraint: str, detail: str):
        self.constraint = constraint
        self.detail = detail
        super().__init__(f"Constraint '{constraint}' violated: {detail}")
