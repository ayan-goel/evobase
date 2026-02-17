"""Template: Remove obvious dead code (unreachable after return/throw).

Detects and removes statements that follow a return or throw in the same
block at the same indentation level.

Example:
    function foo() {
        return bar();
        doSomething();    // dead — removed
        const x = 1;     // dead — removed
    }

This is the most conservative template — only applies to clearly unreachable
lines (same indent, not a closing brace, not a comment).
"""

import re
from typing import Optional

from runner.patchgen.templates.base import PatchTemplate


class DeadCodeTemplate(PatchTemplate):
    name = "dead_code"
    opportunity_type = "dead_code"
    explanation = (
        "Removed unreachable code following a return or throw statement. "
        "Code after unconditional return/throw in the same block can never execute."
    )

    def apply(self, source: str, location: str) -> Optional[str]:
        """Remove dead lines following return/throw at the given location."""
        line_num = self._get_line_number(location)
        if line_num is None:
            return None

        lines = source.splitlines(keepends=True)
        if line_num < 1 or line_num > len(lines):
            return None

        target_line = lines[line_num - 1]
        stripped = target_line.strip()

        # Target line must be a return or throw statement
        if not (stripped.startswith("return ") or stripped.startswith("throw ")):
            return None

        base_indent = len(target_line) - len(target_line.lstrip())

        # Collect dead lines after the return/throw at the same indent level
        dead_range = []
        for i in range(line_num, len(lines)):
            line = lines[i]
            s = line.strip()

            # Stop at closing brace, empty lines, or dedented lines
            if not s or s.startswith("}") or s.startswith("//") or s.startswith("/*"):
                break
            current_indent = len(line) - len(line.lstrip())
            if current_indent < base_indent:
                break
            if current_indent == base_indent:
                dead_range.append(i)

        if not dead_range:
            return None

        # Remove the dead lines
        new_lines = [l for i, l in enumerate(lines) if i not in set(dead_range)]
        return "".join(new_lines)
