"""Template: Reduce intermediate array allocations in hot loops.

Transforms chained .filter().map() or .map().filter() into a single
.reduce() or combined .flatMap() call to avoid creating an intermediate array.

Example:
    const result = items.filter(x => x.active).map(x => x.name);
->
    const result = items.reduce((acc, x) => {
        if (x.active) acc.push(x.name);
        return acc;
    }, []);

Only applies to simple single-property filter/map chains.
"""

import re
from typing import Optional

from runner.patchgen.templates.base import PatchTemplate

# Matches: arr.filter(x => cond).map(x => expr)
_FILTER_MAP_PATTERN = re.compile(
    r"(\w+)\.filter\(\s*(\w+)\s*=>\s*([^)]+)\)\s*\.map\(\s*(\w+)\s*=>\s*([^)]+)\)"
)


class LoopIntermediateTemplate(PatchTemplate):
    name = "loop_intermediate"
    opportunity_type = "loop_intermediate"
    explanation = (
        "Combined .filter().map() chain into a single .reduce() call to "
        "eliminate the intermediate array allocation. The filter+map pattern "
        "allocates two arrays; reduce allocates one."
    )

    def apply(self, source: str, location: str) -> Optional[str]:
        """Replace filter().map() chain with a reduce() call."""
        line_num = self._get_line_number(location)
        if line_num is None:
            return None

        lines = source.splitlines(keepends=True)
        if line_num < 1 or line_num > len(lines):
            return None

        target_line = lines[line_num - 1]
        match = _FILTER_MAP_PATTERN.search(target_line)
        if not match:
            return None

        array_var = match.group(1)
        filter_var = match.group(2)
        filter_cond = match.group(3).strip()
        map_var = match.group(4)
        map_expr = match.group(5).strip()

        # Normalize: replace map_var with filter_var if different
        if map_var != filter_var:
            map_expr = re.sub(r"\b" + re.escape(map_var) + r"\b", filter_var, map_expr)

        indent = len(target_line) - len(target_line.lstrip())
        ind = " " * indent

        new_expr = (
            f"{array_var}.reduce((acc, {filter_var}) => "
            f"{{ if ({filter_cond}) acc.push({map_expr}); return acc; }}, [])"
        )

        new_line = target_line.replace(match.group(0), new_expr)
        lines[line_num - 1] = new_line
        return "".join(lines)
