"""Template: Array.indexOf() membership check -> Array.includes().

Transforms:
    arr.indexOf(x) !== -1
    arr.indexOf(x) >= 0
    arr.indexOf(x) > -1
into:
    arr.includes(x)

And:
    arr.indexOf(x) === -1
    arr.indexOf(x) < 0
into:
    !arr.includes(x)

Note: For Set.has() upgrade (better for large static arrays used in hot paths),
we apply includes() as the safe default since it requires no type change.
The Set upgrade is a separate, higher-risk template.
"""

import re
from typing import Optional

from runner.patchgen.templates.base import PatchTemplate

# Member expression pattern: captures array/object.property chains
_MEMBER_PAT = r"([\w.\[\]]+)"

# Patterns and their replacements
_REPLACEMENTS = [
    # Positive membership
    (re.compile(_MEMBER_PAT + r"\.indexOf\(([^)]+)\)\s*!==\s*-1"), r"\1.includes(\2)"),
    (re.compile(_MEMBER_PAT + r"\.indexOf\(([^)]+)\)\s*>=\s*0"),   r"\1.includes(\2)"),
    (re.compile(_MEMBER_PAT + r"\.indexOf\(([^)]+)\)\s*>\s*-1"),   r"\1.includes(\2)"),
    # Negative membership
    (re.compile(_MEMBER_PAT + r"\.indexOf\(([^)]+)\)\s*===\s*-1"), r"!\1.includes(\2)"),
    (re.compile(_MEMBER_PAT + r"\.indexOf\(([^)]+)\)\s*<\s*0"),    r"!\1.includes(\2)"),
]


class SetMembershipTemplate(PatchTemplate):
    name = "set_membership"
    opportunity_type = "set_membership"
    explanation = (
        "Replaced Array.indexOf() membership check with Array.includes() "
        "for cleaner, intention-revealing code. Both are O(n) but includes() "
        "is more readable and avoids the comparison ceremony."
    )

    def apply(self, source: str, location: str) -> Optional[str]:
        """Apply indexOf -> includes replacement at the specified line."""
        line_num = self._get_line_number(location)
        if line_num is None:
            return None

        lines = source.splitlines(keepends=True)
        if line_num < 1 or line_num > len(lines):
            return None

        original_line = lines[line_num - 1]
        new_line = original_line

        for pattern, replacement in _REPLACEMENTS:
            new_line = pattern.sub(replacement, new_line)

        if new_line == original_line:
            return None

        lines[line_num - 1] = new_line
        return "".join(lines)
