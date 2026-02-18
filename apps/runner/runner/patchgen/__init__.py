"""PatchGen module — patch constraint enforcement and types.

Public API:
    enforce_constraints(patch) -> None (raises ConstraintViolation on failure)
    PatchResult      — patch data container
    ConstraintViolation — raised when a patch violates hard constraints
"""

from runner.patchgen.constraints import enforce_constraints
from runner.patchgen.types import ConstraintViolation, PatchResult

__all__ = ["enforce_constraints", "PatchResult", "ConstraintViolation"]
