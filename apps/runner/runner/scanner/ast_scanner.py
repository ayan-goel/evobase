"""AST-based opportunity scanner using tree-sitter.

Parses JS/TS files into ASTs and walks the tree to detect
structural patterns that indicate optimization opportunities.

This is more precise than heuristics but slower.
Only runs on JS/TS files.
"""

import logging
from pathlib import Path

import tree_sitter
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts

from runner.scanner.types import Opportunity

logger = logging.getLogger(__name__)

# Initialize languages once at module level
_JS_LANG = tree_sitter.Language(tsjs.language())
_TS_LANG = tree_sitter.Language(tsts.language_typescript())

# File extension to language mapping
_LANG_MAP: dict[str, tree_sitter.Language] = {
    ".js": _JS_LANG,
    ".jsx": _JS_LANG,
    ".mjs": _JS_LANG,
    ".ts": _TS_LANG,
    ".tsx": _TS_LANG,
}


def scan_ast(file_path: Path, content: str) -> list[Opportunity]:
    """Run AST-based analysis on a single JS/TS file.

    Parses the file with tree-sitter and walks the tree
    for structural optimization patterns.
    """
    suffix = file_path.suffix
    language = _LANG_MAP.get(suffix)
    if not language:
        return []

    try:
        parser = tree_sitter.Parser(language)
        tree = parser.parse(content.encode("utf-8"))
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", file_path, exc)
        return []

    opportunities: list[Opportunity] = []
    rel_path = str(file_path)

    _walk_tree(tree.root_node, rel_path, opportunities)

    return opportunities


def _walk_tree(
    node: tree_sitter.Node,
    file_path: str,
    opportunities: list[Opportunity],
) -> None:
    """Recursively walk the AST and check each node for patterns."""
    # Check this node against all detectors
    for detector in _DETECTORS:
        opp = detector(node, file_path)
        if opp:
            opportunities.append(opp)

    # Recurse into children
    for child in node.children:
        _walk_tree(child, file_path, opportunities)


def _detect_indexof_comparison(
    node: tree_sitter.Node, file_path: str
) -> Opportunity | None:
    """Detect .indexOf() used in binary comparisons (AST-precise).

    Matches patterns like: arr.indexOf(x) !== -1
    The AST structure is: binary_expression with call_expression containing
    member_expression with property "indexOf".
    """
    if node.type != "binary_expression":
        return None

    # Check if left side is a call to .indexOf
    left = node.child_by_field_name("left")
    if not left or left.type != "call_expression":
        return None

    func = left.child_by_field_name("function")
    if not func or func.type != "member_expression":
        return None

    prop = func.child_by_field_name("property")
    if not prop:
        return None

    prop_text = prop.text.decode("utf-8") if prop.text else ""
    if prop_text != "indexOf":
        return None

    line = node.start_point[0] + 1
    return Opportunity(
        type="set_membership",
        location=f"{file_path}:{line}",
        rationale="Array.indexOf comparison detected via AST; consider Set.has() for O(1) membership check",
        risk_score=0.15,
        source="ast",
    )


def _detect_redundant_spread_in_loop(
    node: tree_sitter.Node, file_path: str
) -> Opportunity | None:
    """Detect object spread inside for/while loops.

    Pattern: { ...obj, key: value } inside a loop body.
    Each iteration creates a new object copy, which is O(n) per iteration.
    """
    if node.type != "spread_element":
        return None

    # Walk up to check if we're inside a loop body
    parent = node.parent
    depth = 0
    while parent and depth < 20:
        if parent.type in ("for_statement", "for_in_statement", "while_statement", "do_statement"):
            line = node.start_point[0] + 1
            return Opportunity(
                type="redundant_spread",
                location=f"{file_path}:{line}",
                rationale="Object spread inside a loop; each iteration copies the full object. Consider mutating or accumulating differently",
                risk_score=0.35,
                source="ast",
            )
        parent = parent.parent
        depth += 1

    return None


def _detect_array_find_in_loop(
    node: tree_sitter.Node, file_path: str
) -> Opportunity | None:
    """Detect Array.find() inside loops.

    Linear search inside a loop is O(n*m). Converting the array to a
    Map before the loop makes lookups O(1).
    """
    if node.type != "call_expression":
        return None

    func = node.child_by_field_name("function")
    if not func or func.type != "member_expression":
        return None

    prop = func.child_by_field_name("property")
    if not prop:
        return None

    prop_text = prop.text.decode("utf-8") if prop.text else ""
    if prop_text != "find":
        return None

    # Check if inside a loop
    parent = node.parent
    depth = 0
    while parent and depth < 20:
        if parent.type in ("for_statement", "for_in_statement", "while_statement", "do_statement"):
            line = node.start_point[0] + 1
            return Opportunity(
                type="unindexed_find",
                location=f"{file_path}:{line}",
                rationale="Array.find() inside a loop creates O(n*m) complexity; pre-index with a Map for O(1) lookups",
                risk_score=0.25,
                source="ast",
            )
        parent = parent.parent
        depth += 1

    return None


# List of all AST detector functions
_DETECTORS = [
    _detect_indexof_comparison,
    _detect_redundant_spread_in_loop,
    _detect_array_find_in_loop,
]
