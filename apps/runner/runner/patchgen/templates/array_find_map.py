"""Template: Array.find() in hot loop -> pre-index with Map.

Adds a Map index built from the array before the loop,
replacing data.find(d => d.id === x) with map.get(x).

This converts O(n*m) to O(n+m).

Only applies when the .find() callback compares a single property (.id, .key, etc.).
"""

import re
from typing import Optional

from runner.patchgen.templates.base import PatchTemplate

# Matches: data.find(d => d.id === target)  or  data.find(d => d.id == target)
_FIND_PATTERN = re.compile(
    r"(\w+)\.find\(\s*(\w+)\s*=>\s*\2\.(\w+)\s*===?\s*([^)]+)\)"
)


class ArrayFindMapTemplate(PatchTemplate):
    name = "array_find_map"
    opportunity_type = "unindexed_find"
    explanation = (
        "Pre-indexed the array with a Map before the loop, replacing "
        "Array.find() (O(n) per lookup) with Map.get() (O(1) per lookup). "
        "This converts O(n*m) loop complexity to O(n+m)."
    )

    def apply(self, source: str, location: str) -> Optional[str]:
        """Replace Array.find() in a loop with a pre-built Map lookup."""
        line_num = self._get_line_number(location)
        if line_num is None:
            return None

        lines = source.splitlines(keepends=True)
        if line_num < 1 or line_num > len(lines):
            return None

        target_line = lines[line_num - 1]
        match = _FIND_PATTERN.search(target_line)
        if not match:
            return None

        array_var = match.group(1)
        key_prop = match.group(3)
        lookup_key = match.group(4).strip()

        # Find the loop header above the current line
        loop_line_idx = None
        for i in range(line_num - 2, max(line_num - 20, -1), -1):
            stripped = lines[i].strip()
            if re.match(r"^(for|while|do)\b", stripped):
                loop_line_idx = i
                break

        if loop_line_idx is None:
            return None

        map_var = f"_{array_var}ByKey"
        indent = len(lines[loop_line_idx]) - len(lines[loop_line_idx].lstrip())
        indent_str = " " * indent

        map_line = (
            f"{indent_str}const {map_var} = new Map("
            f"{array_var}.map(item => [item.{key_prop}, item]));\n"
        )

        # Replace the find call in the target line with map.get()
        new_target = target_line.replace(
            match.group(0),
            f"{map_var}.get({lookup_key})",
        )
        lines[line_num - 1] = new_target

        # Insert the Map before the loop
        lines.insert(loop_line_idx, map_line)
        return "".join(lines)
