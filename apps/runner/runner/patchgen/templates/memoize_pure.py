"""Template: Wrap a pure function with a simple memoization cache.

Transforms:
    function compute(x) {
        return heavyCalculation(x);
    }

Into:
    const _computeCache = new Map();
    function compute(x) {
        const _cacheKey = JSON.stringify(x);
        if (_computeCache.has(_cacheKey)) return _computeCache.get(_cacheKey);
        const _result = heavyCalculation(x);
        _computeCache.set(_cacheKey, _result);
        return _result;
    }

Only applies to functions with a single return statement and no side effects
(detected as: no assignments, no I/O calls, no this references).
"""

import re
from typing import Optional

from runner.patchgen.templates.base import PatchTemplate

# Matches: function name(...) { ... }
_FUNC_DECL_PATTERN = re.compile(r"^(\s*)function\s+(\w+)\s*\(([^)]*)\)\s*\{")

# Side-effect indicators that disqualify a function from memoization
_SIDE_EFFECT_PATTERNS = [
    re.compile(r"\bthis\b"),
    re.compile(r"\bconsole\.\w+\("),
    re.compile(r"\bfetch\b|\baxios\b"),
    re.compile(r"fs\.\w+\("),
    re.compile(r"\bawait\b"),
    re.compile(r"=(?!=)"),  # assignment (simplistic, catches most)
]


class MemoizePureTemplate(PatchTemplate):
    name = "memoize_pure"
    opportunity_type = "memoize_pure"
    explanation = (
        "Wrapped function with a simple Map-based memoization cache. "
        "If the function is called repeatedly with the same arguments, "
        "subsequent calls return the cached result without recomputing."
    )

    def apply(self, source: str, location: str) -> Optional[str]:
        """Add memoization wrapper to the function at the given location."""
        line_num = self._get_line_number(location)
        if line_num is None:
            return None

        lines = source.splitlines(keepends=True)
        if line_num < 1 or line_num > len(lines):
            return None

        target_line = lines[line_num - 1]
        header_match = _FUNC_DECL_PATTERN.match(target_line)
        if not header_match:
            return None

        indent = header_match.group(1)
        func_name = header_match.group(2)

        # Find the function body (closing brace)
        body_start = line_num  # 0-indexed: lines[line_num - 1] is the header
        depth = 0
        body_end = None
        for i in range(line_num - 1, min(line_num + 50, len(lines))):
            depth += lines[i].count("{") - lines[i].count("}")
            if depth <= 0 and i > line_num - 1:
                body_end = i
                break

        if body_end is None:
            return None

        # Check for side effects in function body
        body = "".join(lines[line_num:body_end])
        for pattern in _SIDE_EFFECT_PATTERNS:
            if pattern.search(body):
                return None

        # Must have exactly one return statement
        return_count = len(re.findall(r"\breturn\b", body))
        if return_count != 1:
            return None

        # Build the memoized version
        cache_var = f"_{func_name}Cache"
        cache_decl = f"{indent}const {cache_var} = new Map();\n"

        memo_prefix = (
            f"{indent}  const _cacheKey = JSON.stringify(arguments[0]);\n"
            f"{indent}  if ({cache_var}.has(_cacheKey)) return {cache_var}.get(_cacheKey);\n"
        )

        # Replace "return expr;" with caching + return
        memo_return = re.compile(r"^(\s*)return\s+(.+);", re.MULTILINE)

        def wrap_return(m: re.Match) -> str:
            ret_indent = m.group(1)
            ret_expr = m.group(2)
            return (
                f"{ret_indent}const _result = {ret_expr};\n"
                f"{ret_indent}{cache_var}.set(_cacheKey, _result);\n"
                f"{ret_indent}return _result;"
            )

        new_body = memo_return.sub(wrap_return, body)

        new_lines = (
            lines[:line_num - 1]
            + [cache_decl, target_line]
            + [memo_prefix]
            + new_body.splitlines(keepends=True)
            + lines[body_end:]
        )
        return "".join(new_lines)
