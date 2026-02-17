"""Template: String concatenation in loop -> Array.join().

Transforms patterns like:
    let result = "";
    for (const x of arr) {
        result += transform(x);
    }

Into:
    const result = arr.map(x => transform(x)).join("");

This template detects simple += patterns and wraps them.
Only applies when the accumulator variable is initialized to "" before the loop.
"""

import re
from typing import Optional

from runner.patchgen.templates.base import PatchTemplate

_INIT_PATTERN = re.compile(r'(let|var)\s+(\w+)\s*=\s*["\'][\s]*["\']')
_FOR_OF_PATTERN = re.compile(r"for\s*\((?:const|let|var)\s+(\w+)\s+of\s+(\w+)\)")
_CONCAT_PATTERN = re.compile(r"(\w+)\s*\+=\s*(.+?);?\s*$")


class StringConcatLoopTemplate(PatchTemplate):
    name = "string_concat_loop"
    opportunity_type = "string_concat_loop"
    explanation = (
        "Replaced string concatenation in a loop with Array.map().join(). "
        "Each += in a loop allocates a new string; map+join pre-allocates "
        "and performs a single join operation."
    )

    def apply(self, source: str, location: str) -> Optional[str]:
        """Detect and transform a simple for-of + += pattern."""
        line_num = self._get_line_number(location)
        if line_num is None:
            return None

        lines = source.splitlines(keepends=True)
        if line_num < 1 or line_num > len(lines):
            return None

        concat_line = lines[line_num - 1]
        concat_match = _CONCAT_PATTERN.search(concat_line)
        if not concat_match:
            return None

        accum_var = concat_match.group(1)
        concat_expr = concat_match.group(2).strip()

        # Scan backwards for the for-of loop header
        loop_line_idx = None
        for i in range(line_num - 2, max(line_num - 15, -1), -1):
            if _FOR_OF_PATTERN.search(lines[i]):
                loop_line_idx = i
                break

        if loop_line_idx is None:
            return None

        loop_match = _FOR_OF_PATTERN.search(lines[loop_line_idx])
        iter_var = loop_match.group(1)
        array_var = loop_match.group(2)

        # Scan backwards for the accumulator init
        init_line_idx = None
        for i in range(loop_line_idx - 1, max(loop_line_idx - 5, -1), -1):
            m = _INIT_PATTERN.search(lines[i])
            if m and m.group(2) == accum_var:
                init_line_idx = i
                break

        if init_line_idx is None:
            return None

        # Build the replacement: const result = arr.map(x => expr).join("");
        indent = len(lines[init_line_idx]) - len(lines[init_line_idx].lstrip())
        indent_str = " " * indent
        body_expr = concat_expr.replace(iter_var, iter_var)

        new_line = (
            f"{indent_str}const {accum_var} = {array_var}"
            f".map({iter_var} => {body_expr}).join(\"\");\n"
        )

        # Find the closing brace of the for loop
        close_brace_idx = None
        depth = 0
        for i in range(loop_line_idx, min(loop_line_idx + 20, len(lines))):
            depth += lines[i].count("{") - lines[i].count("}")
            if depth <= 0:
                close_brace_idx = i
                break

        if close_brace_idx is None:
            return None

        # Replace: remove init + loop + body + close brace, insert single line
        new_lines = (
            lines[:init_line_idx]
            + [new_line]
            + lines[close_brace_idx + 1:]
        )
        return "".join(new_lines)
