"""Unit tests for the AST scanner."""

from pathlib import Path

import pytest

from runner.scanner.ast_scanner import scan_ast


class TestIndexOfAST:
    def test_detects_indexof_comparison(self):
        code = 'if (arr.indexOf(x) !== -1) { doSomething(); }'
        opps = scan_ast(Path("test.js"), code)
        sm_opps = [o for o in opps if o.type == "set_membership"]
        assert len(sm_opps) >= 1

    def test_detects_indexof_gte_zero(self):
        code = 'const found = list.indexOf(item) >= 0;'
        opps = scan_ast(Path("test.js"), code)
        sm_opps = [o for o in opps if o.type == "set_membership"]
        assert len(sm_opps) >= 1

    def test_source_is_ast(self):
        code = 'if (arr.indexOf(x) !== -1) {}'
        opps = scan_ast(Path("test.js"), code)
        assert all(o.source == "ast" for o in opps)

    def test_risk_lower_than_heuristic(self):
        code = 'if (arr.indexOf(x) !== -1) {}'
        opps = scan_ast(Path("test.js"), code)
        sm_opps = [o for o in opps if o.type == "set_membership"]
        assert all(o.risk_score <= 0.2 for o in sm_opps)


class TestSpreadInLoopAST:
    def test_detects_spread_in_for_loop(self):
        code = """
for (let i = 0; i < items.length; i++) {
  result = { ...result, [items[i].key]: items[i].value };
}
"""
        opps = scan_ast(Path("test.ts"), code)
        spread_opps = [o for o in opps if o.type == "redundant_spread"]
        assert len(spread_opps) >= 1

    def test_spread_outside_loop_not_flagged(self):
        code = 'const merged = { ...defaults, ...overrides };'
        opps = scan_ast(Path("test.ts"), code)
        spread_opps = [o for o in opps if o.type == "redundant_spread"]
        assert len(spread_opps) == 0


class TestFindInLoopAST:
    def test_detects_find_in_for_loop(self):
        code = """
for (let i = 0; i < targets.length; i++) {
  const match = data.find(d => d.id === targets[i].id);
}
"""
        opps = scan_ast(Path("test.js"), code)
        find_opps = [o for o in opps if o.type == "unindexed_find"]
        assert len(find_opps) >= 1

    def test_find_outside_loop_not_flagged(self):
        code = 'const user = users.find(u => u.id === targetId);'
        opps = scan_ast(Path("test.js"), code)
        find_opps = [o for o in opps if o.type == "unindexed_find"]
        assert len(find_opps) == 0


class TestFileExtensions:
    def test_js_file_parsed(self):
        code = 'if (arr.indexOf(x) !== -1) {}'
        opps = scan_ast(Path("test.js"), code)
        assert len(opps) >= 1

    def test_ts_file_parsed(self):
        code = 'if (arr.indexOf(x) !== -1) {}'
        opps = scan_ast(Path("test.ts"), code)
        assert len(opps) >= 1

    def test_tsx_file_parsed(self):
        code = 'if (arr.indexOf(x) !== -1) {}'
        opps = scan_ast(Path("test.tsx"), code)
        assert len(opps) >= 1

    def test_jsx_file_parsed(self):
        code = 'if (arr.indexOf(x) !== -1) {}'
        opps = scan_ast(Path("test.jsx"), code)
        assert len(opps) >= 1

    def test_py_file_skipped(self):
        code = 'x in arr'
        opps = scan_ast(Path("test.py"), code)
        assert len(opps) == 0

    def test_css_file_skipped(self):
        code = '.class { color: red; }'
        opps = scan_ast(Path("test.css"), code)
        assert len(opps) == 0


class TestASTMetadata:
    def test_location_includes_line(self):
        code = '// comment\nif (arr.indexOf(x) !== -1) {}'
        opps = scan_ast(Path("src/utils.js"), code)
        assert opps[0].location == "src/utils.js:2"

    def test_opportunity_to_dict(self):
        code = 'if (arr.indexOf(x) !== -1) {}'
        opps = scan_ast(Path("test.js"), code)
        d = opps[0].to_dict()
        assert "type" in d
        assert "location" in d
        assert "rationale" in d
        assert "risk_score" in d
        assert "source" in d
