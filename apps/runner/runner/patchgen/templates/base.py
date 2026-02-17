"""Base class for all patch templates.

Each template receives the original source, the opportunity location,
and returns a modified source string (or None if it cannot apply).
The orchestrator computes the diff from the original vs modified.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class PatchTemplate(ABC):
    """Abstract base class for all patch templates.

    apply() takes the original file content and an opportunity location
    (e.g., "42" for line 42) and returns the modified content if the
    transformation applies, or None if it cannot be applied safely.
    """

    #: Human-readable name for this template
    name: str = ""

    #: Which scanner opportunity type this template handles
    opportunity_type: str = ""

    #: Conservative explanation of the change
    explanation: str = ""

    @abstractmethod
    def apply(self, source: str, location: str) -> Optional[str]:
        """Apply the patch to source code at the given location.

        Args:
            source: Full file content as a string.
            location: Line number string (e.g., "42") from the opportunity.

        Returns:
            Modified source string if the patch applies, None otherwise.
        """
        ...

    def _get_line_number(self, location: str) -> Optional[int]:
        """Extract the line number from a 'file:line' location string."""
        try:
            return int(location.split(":")[-1])
        except (ValueError, IndexError):
            return None
