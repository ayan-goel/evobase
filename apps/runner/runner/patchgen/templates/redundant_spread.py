"""Template: Redundant object spread in loop -> Object.assign accumulation.

Transforms:
    let acc = {};
    for (const item of items) {
        acc = { ...acc, [item.key]: item.value };
    }
Into:
    const acc = {};
    for (const item of items) {
        acc[item.key] = item.value;
    }

Replacing full object copy per iteration with direct property assignment.
"""

import re
from typing import Optional

from runner.patchgen.templates.base import PatchTemplate

# Matches: acc = { ...acc, [key]: value } or acc = { ...acc, key: value }
_SPREAD_PATTERN = re.compile(
    r"(\w+)\s*=\s*\{\s*\.\.\.(\w+)\s*,\s*(?:\[([^\]]+)\]|(\w+))\s*:\s*([^}]+)\}\s*;?"
)


class RedundantSpreadTemplate(PatchTemplate):
    name = "redundant_spread"
    opportunity_type = "redundant_spread"
    explanation = (
        "Replaced full object spread in loop with direct property assignment. "
        "Each `{ ...obj }` creates a shallow copy of the entire object. "
        "Direct assignment mutates in-place, avoiding O(n) allocation per iteration."
    )

    def apply(self, source: str, location: str) -> Optional[str]:
        """Replace spread accumulation with direct property assignment."""
        line_num = self._get_line_number(location)
        if line_num is None:
            return None

        lines = source.splitlines(keepends=True)
        if line_num < 1 or line_num > len(lines):
            return None

        target_line = lines[line_num - 1]
        match = _SPREAD_PATTERN.search(target_line)
        if not match:
            return None

        accum_var = match.group(1)
        spread_var = match.group(2)

        # Only safe if accumulating into itself: acc = { ...acc, ... }
        if accum_var != spread_var:
            return None

        key_expr = match.group(3) or match.group(4)
        value_expr = match.group(5).strip()

        indent = len(target_line) - len(target_line.lstrip())
        indent_str = " " * indent

        if match.group(3):
            # Computed key: acc[key] = value
            new_line = f"{indent_str}{accum_var}[{key_expr}] = {value_expr};\n"
        else:
            # Static key: acc.key = value
            new_line = f"{indent_str}{accum_var}.{key_expr} = {value_expr};\n"

        lines[line_num - 1] = new_line
        return "".join(lines)
