"""PatchGen module — template-based patch generation.

Public API:
    generate_patch(opportunity, repo_dir) -> Optional[PatchResult]
"""

from runner.patchgen.generator import generate_patch
from runner.patchgen.types import ConstraintViolation, PatchResult

__all__ = ["generate_patch", "PatchResult", "ConstraintViolation"]
