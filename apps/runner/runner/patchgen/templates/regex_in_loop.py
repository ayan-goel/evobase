"""Template: Hoist regex compilation out of loops.

Transforms:
    for (...) {
        const match = new RegExp("pattern").test(str);
    }
Into:
    const _re = /pattern/;
    for (...) {
        const match = _re.test(str);
    }

Only handles new RegExp("literal") patterns (not dynamic regexes).
"""

import re
from typing import Optional

from runner.patchgen.templates.base import PatchTemplate

_NEW_REGEXP_PATTERN = re.compile(r'new\s+RegExp\s*\(\s*["\']([^"\']+)["\']\s*(?:,\s*["\']([gimsuy]*)["\'])?\s*\)')


class RegexInLoopTemplate(PatchTemplate):
    name = "regex_in_loop"
    opportunity_type = "regex_in_loop"
    explanation = (
        "Hoisted RegExp compilation outside the loop. Creating a RegExp "
        "object inside a loop recompiles the pattern on every iteration. "
        "Hoisting to a constant compiles it once."
    )

    def apply(self, source: str, location: str) -> Optional[str]:
        """Hoist a new RegExp() from inside a loop to a const before the loop."""
        line_num = self._get_line_number(location)
        if line_num is None:
            return None

        lines = source.splitlines(keepends=True)
        if line_num < 1 or line_num > len(lines):
            return None

        target_line = lines[line_num - 1]
        match = _NEW_REGEXP_PATTERN.search(target_line)
        if not match:
            return None

        pattern_str = match.group(1)
        flags = match.group(2) or ""

        # Find the loop header above the current line
        loop_line_idx = None
        for i in range(line_num - 2, max(line_num - 15, -1), -1):
            stripped = lines[i].strip()
            if re.match(r"^(for|while|do)\b", stripped):
                loop_line_idx = i
                break

        if loop_line_idx is None:
            return None

        # Generate a const name based on the pattern
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", pattern_str[:20])
        const_name = f"_re_{safe_name}" if safe_name else "_re"
        const_name = re.sub(r"_+", "_", const_name).strip("_")

        # Build the regex literal
        regex_literal = f"/{pattern_str}/{flags}"
        indent = len(lines[loop_line_idx]) - len(lines[loop_line_idx].lstrip())
        const_line = " " * indent + f"const {const_name} = {regex_literal};\n"

        # Replace new RegExp(...) in the target line with the const name
        new_target = target_line.replace(match.group(0), const_name)
        lines[line_num - 1] = new_target

        # Insert the const before the loop
        lines.insert(loop_line_idx, const_line)
        return "".join(lines)
