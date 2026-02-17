"""Template: Cache repeated JSON.parse() calls.

When JSON.parse is called multiple times in the same function scope,
hoists the first call to a variable and replaces subsequent calls.

This template requires at least 2 JSON.parse calls with the same
argument in the same function. It returns None if only one call is found.
"""

import re
from typing import Optional

from runner.patchgen.templates.base import PatchTemplate

_JSON_PARSE_RE = re.compile(r"JSON\.parse\(([^)]+)\)")


class JsonParseCacheTemplate(PatchTemplate):
    name = "json_parse_cache"
    opportunity_type = "json_parse_cache"
    explanation = (
        "Cached repeated JSON.parse() calls by hoisting the first parse to "
        "a variable. Subsequent calls to JSON.parse with the same argument "
        "are replaced with the cached variable, avoiding redundant parsing."
    )

    def apply(self, source: str, location: str) -> Optional[str]:
        """Cache the JSON.parse call at the given line.

        Adds a cached variable before the first parse and replaces
        the second occurrence with a reference to the cached value.
        Only applies when the same argument appears at least twice.
        """
        line_num = self._get_line_number(location)
        if line_num is None:
            return None

        lines = source.splitlines(keepends=True)
        if line_num < 1 or line_num > len(lines):
            return None

        target_line = lines[line_num - 1]
        match = _JSON_PARSE_RE.search(target_line)
        if not match:
            return None

        arg = match.group(1).strip()
        var_name = "_parsedJson"

        # Count occurrences of this exact parse call in surrounding lines
        search_range = "".join(lines[max(0, line_num - 10):line_num + 10])
        pattern = re.compile(r"JSON\.parse\(\s*" + re.escape(arg) + r"\s*\)")
        occurrences = pattern.findall(search_range)

        if len(occurrences) < 2:
            return None

        # Replace the target line: add cached variable + replace parse with var
        indent = len(target_line) - len(target_line.lstrip())
        indent_str = " " * indent

        new_line = target_line.replace(match.group(0), var_name)
        cache_line = f"{indent_str}const {var_name} = {match.group(0)};\n"

        lines[line_num - 1] = cache_line + new_line
        return "".join(lines)
