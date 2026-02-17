"""Golden tests for scanner — input files mapped to expected opportunities.

Each test reads a fixture file, scans it, and verifies the expected
opportunities are found. These serve as regression tests.
"""

from pathlib import Path

import pytest

from runner.scanner.heuristics import scan_heuristics
from runner.scanner.ast_scanner import scan_ast

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "scanner-inputs"


class TestSetMembershipGolden:
    """set-membership.ts should produce set_membership opportunities."""

    @pytest.fixture
    def content(self):
        return (FIXTURES_DIR / "set-membership.ts").read_text()

    def test_heuristic_finds_indexof_patterns(self, content):
        opps = scan_heuristics(Path("set-membership.ts"), content)
        sm_opps = [o for o in opps if o.type == "set_membership"]
        assert len(sm_opps) >= 3  # indexOf !== -1, >= 0, === -1

    def test_ast_finds_indexof_comparisons(self, content):
        opps = scan_ast(Path("set-membership.ts"), content)
        sm_opps = [o for o in opps if o.type == "set_membership"]
        assert len(sm_opps) >= 2

    def test_ast_has_lower_risk_than_heuristic(self, content):
        h_opps = scan_heuristics(Path("set-membership.ts"), content)
        a_opps = scan_ast(Path("set-membership.ts"), content)

        h_risks = [o.risk_score for o in h_opps if o.type == "set_membership"]
        a_risks = [o.risk_score for o in a_opps if o.type == "set_membership"]

        if h_risks and a_risks:
            assert min(a_risks) < min(h_risks)

    def test_includes_not_flagged(self, content):
        """Array.includes should not trigger set_membership."""
        opps = scan_heuristics(Path("set-membership.ts"), content)
        # The includes() call on line 23 should not create an opportunity
        for opp in opps:
            if opp.type == "set_membership":
                assert "includes" not in opp.rationale.lower() or "indexOf" in opp.rationale


class TestJsonParseGolden:
    """json-parse.js should produce json_parse_cache opportunities."""

    @pytest.fixture
    def content(self):
        return (FIXTURES_DIR / "json-parse.js").read_text()

    def test_heuristic_finds_json_parse(self, content):
        opps = scan_heuristics(Path("json-parse.js"), content)
        jp_opps = [o for o in opps if o.type == "json_parse_cache"]
        assert len(jp_opps) >= 3  # Three JSON.parse calls

    def test_risk_score_is_reasonable(self, content):
        opps = scan_heuristics(Path("json-parse.js"), content)
        for opp in opps:
            if opp.type == "json_parse_cache":
                assert 0.0 <= opp.risk_score <= 0.5


class TestLoopPatternsGolden:
    """loop-patterns.ts should trigger multiple loop-related patterns."""

    @pytest.fixture
    def content(self):
        return (FIXTURES_DIR / "loop-patterns.ts").read_text()

    def test_heuristic_finds_string_concat_in_loop(self, content):
        opps = scan_heuristics(Path("loop-patterns.ts"), content)
        sc_opps = [o for o in opps if o.type == "string_concat_loop"]
        assert len(sc_opps) >= 1

    def test_heuristic_finds_regex_in_loop(self, content):
        opps = scan_heuristics(Path("loop-patterns.ts"), content)
        re_opps = [o for o in opps if o.type == "regex_in_loop"]
        assert len(re_opps) >= 1

    def test_regex_outside_loop_not_flagged(self, content):
        """The EMAIL_RE constant outside a loop should not trigger."""
        opps = scan_heuristics(Path("loop-patterns.ts"), content)
        for opp in opps:
            if opp.type == "regex_in_loop":
                # Should not be on the line with EMAIL_RE
                assert "EMAIL_RE" not in opp.location

    def test_ast_finds_find_in_loop(self, content):
        opps = scan_ast(Path("loop-patterns.ts"), content)
        find_opps = [o for o in opps if o.type == "unindexed_find"]
        assert len(find_opps) >= 1

    def test_ast_finds_spread_in_loop(self, content):
        opps = scan_ast(Path("loop-patterns.ts"), content)
        spread_opps = [o for o in opps if o.type == "redundant_spread"]
        assert len(spread_opps) >= 1


class TestSyncFsGolden:
    """sync-fs.ts should trigger sync_fs_in_handler opportunities."""

    @pytest.fixture
    def content(self):
        return (FIXTURES_DIR / "sync-fs.ts").read_text()

    def test_heuristic_finds_sync_fs_calls(self, content):
        opps = scan_heuristics(Path("sync-fs.ts"), content)
        fs_opps = [o for o in opps if o.type == "sync_fs_in_handler"]
        assert len(fs_opps) >= 3  # readFileSync, existsSync, writeFileSync

    def test_risk_score_for_sync_fs(self, content):
        opps = scan_heuristics(Path("sync-fs.ts"), content)
        for opp in opps:
            if opp.type == "sync_fs_in_handler":
                assert opp.risk_score == 0.4


class TestCleanFileGolden:
    """clean-file.ts should NOT produce any opportunities."""

    @pytest.fixture
    def content(self):
        return (FIXTURES_DIR / "clean-file.ts").read_text()

    def test_heuristic_finds_nothing(self, content):
        opps = scan_heuristics(Path("clean-file.ts"), content)
        assert len(opps) == 0

    def test_ast_finds_nothing(self, content):
        opps = scan_ast(Path("clean-file.ts"), content)
        assert len(opps) == 0
