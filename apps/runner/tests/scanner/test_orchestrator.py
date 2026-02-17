"""Tests for the scanner orchestrator — deduplication, ranking, file collection."""

import json
import time
from pathlib import Path

import pytest

from runner.scanner import scan
from runner.scanner.orchestrator import (
    SCANNABLE_EXTENSIONS,
    SKIP_DIRS,
    _collect_files,
    _deduplicate,
)
from runner.scanner.types import Opportunity, ScanResult

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "scanner-inputs"


class TestCollectFiles:
    def test_collects_js_files(self, tmp_path):
        (tmp_path / "app.js").write_text("const x = 1;")
        files = _collect_files(tmp_path)
        assert len(files) == 1

    def test_collects_ts_files(self, tmp_path):
        (tmp_path / "app.ts").write_text("const x: number = 1;")
        files = _collect_files(tmp_path)
        assert len(files) == 1

    def test_collects_tsx_files(self, tmp_path):
        (tmp_path / "App.tsx").write_text("export default function App() {}")
        files = _collect_files(tmp_path)
        assert len(files) == 1

    def test_ignores_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "lodash"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {};")
        (tmp_path / "app.js").write_text("const x = 1;")
        files = _collect_files(tmp_path)
        assert len(files) == 1
        assert "node_modules" not in files[0].relative_to(tmp_path).parts

    def test_ignores_dist(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "bundle.js").write_text("compiled code")
        files = _collect_files(tmp_path)
        assert len(files) == 0

    def test_ignores_non_js_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "style.css").write_text("body {}")
        (tmp_path / "config.json").write_text("{}")
        files = _collect_files(tmp_path)
        assert len(files) == 0

    def test_skips_large_files(self, tmp_path):
        large_file = tmp_path / "huge.js"
        large_file.write_text("x" * (256 * 1024 + 1))
        files = _collect_files(tmp_path)
        assert len(files) == 0

    def test_nested_directories(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib").mkdir()
        (tmp_path / "src" / "app.ts").write_text("const x = 1;")
        (tmp_path / "src" / "lib" / "utils.ts").write_text("export {};")
        files = _collect_files(tmp_path)
        assert len(files) == 2

    def test_returns_sorted(self, tmp_path):
        (tmp_path / "b.ts").write_text("b")
        (tmp_path / "a.ts").write_text("a")
        files = _collect_files(tmp_path)
        assert files[0].name == "a.ts"


class TestDeduplicate:
    def test_removes_exact_duplicates(self):
        opps = [
            Opportunity("set_membership", "file.ts:10", "reason", 0.2, "heuristic"),
            Opportunity("set_membership", "file.ts:10", "reason", 0.15, "ast"),
        ]
        deduped = _deduplicate(opps)
        assert len(deduped) == 1

    def test_prefers_ast_over_heuristic(self):
        opps = [
            Opportunity("set_membership", "file.ts:10", "heuristic reason", 0.2, "heuristic"),
            Opportunity("set_membership", "file.ts:10", "ast reason", 0.15, "ast"),
        ]
        deduped = _deduplicate(opps)
        assert deduped[0].source == "ast"

    def test_keeps_different_types(self):
        opps = [
            Opportunity("set_membership", "file.ts:10", "r1", 0.2, "heuristic"),
            Opportunity("json_parse_cache", "file.ts:10", "r2", 0.3, "heuristic"),
        ]
        deduped = _deduplicate(opps)
        assert len(deduped) == 2

    def test_keeps_different_locations(self):
        opps = [
            Opportunity("set_membership", "file.ts:10", "r1", 0.2, "heuristic"),
            Opportunity("set_membership", "file.ts:20", "r2", 0.2, "heuristic"),
        ]
        deduped = _deduplicate(opps)
        assert len(deduped) == 2

    def test_empty_list(self):
        assert _deduplicate([]) == []


class TestScanEnd2End:
    """End-to-end tests running the full scanner on fixture files."""

    def test_scan_fixture_directory(self):
        result = scan(FIXTURES_DIR)

        assert isinstance(result, ScanResult)
        assert result.files_scanned >= 4  # At least our 4 non-clean fixtures + clean
        assert len(result.opportunities) > 0

    def test_opportunities_sorted_by_risk(self):
        result = scan(FIXTURES_DIR)
        risks = [o.risk_score for o in result.opportunities]
        assert risks == sorted(risks)

    def test_clean_file_contributes_no_opportunities(self):
        """Opportunities should not come from clean-file.ts."""
        result = scan(FIXTURES_DIR)
        for opp in result.opportunities:
            assert "clean-file.ts" not in opp.location

    def test_scan_result_to_dict(self):
        result = scan(FIXTURES_DIR)
        d = result.to_dict()
        assert "opportunities" in d
        assert "opportunity_count" in d
        assert "files_scanned" in d
        assert "scan_duration_seconds" in d
        assert d["opportunity_count"] == len(d["opportunities"])

    def test_scan_duration_is_reasonable(self):
        """Scanner should complete in under 5 seconds on fixtures."""
        start = time.monotonic()
        result = scan(FIXTURES_DIR)
        duration = time.monotonic() - start

        assert duration < 5.0
        assert result.scan_duration_seconds < 5.0

    def test_all_opportunity_types_have_valid_fields(self):
        result = scan(FIXTURES_DIR)
        for opp in result.opportunities:
            assert opp.type is not None
            assert ":" in opp.location  # file:line format
            assert opp.rationale
            assert 0.0 <= opp.risk_score <= 1.0
            assert opp.source in ("heuristic", "ast")


class TestScanEmptyRepo:
    def test_empty_directory(self, tmp_path):
        result = scan(tmp_path)
        assert result.files_scanned == 0
        assert len(result.opportunities) == 0

    def test_no_js_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        result = scan(tmp_path)
        assert result.files_scanned == 0


class TestScanRegression:
    """Regression tests to ensure scanner output is stable.

    These assert specific counts. Update if scanner logic changes.
    """

    def test_set_membership_count(self):
        result = scan(FIXTURES_DIR)
        sm_opps = [o for o in result.opportunities if o.type == "set_membership"]
        # At least 2 deduplicated (AST wins where both detect)
        assert len(sm_opps) >= 2

    def test_sync_fs_count(self):
        result = scan(FIXTURES_DIR)
        fs_opps = [o for o in result.opportunities if o.type == "sync_fs_in_handler"]
        assert len(fs_opps) >= 3

    def test_json_parse_count(self):
        result = scan(FIXTURES_DIR)
        jp_opps = [o for o in result.opportunities if o.type == "json_parse_cache"]
        assert len(jp_opps) >= 3
