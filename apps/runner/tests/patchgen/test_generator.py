"""Tests for the patch generator orchestrator."""

from pathlib import Path
from unittest.mock import patch

import pytest

from runner.patchgen import generate_patch
from runner.patchgen.types import ConstraintViolation
from runner.scanner.types import Opportunity


def _make_opp(opp_type: str, location: str) -> Opportunity:
    return Opportunity(
        type=opp_type,
        location=location,
        rationale="test",
        risk_score=0.2,
        source="heuristic",
    )


class TestGeneratePatch:
    def test_generates_patch_for_set_membership(self, tmp_path):
        (tmp_path / "src").mkdir()
        source_file = tmp_path / "src" / "utils.ts"
        source_file.write_text('if (arr.indexOf(x) !== -1) { return true; }\n')

        opp = _make_opp("set_membership", "src/utils.ts:1")
        result = generate_patch(opp, tmp_path)

        assert result is not None
        assert "includes" in result.diff
        assert result.touched_files == ["src/utils.ts"]
        assert result.template_name == "set_membership"
        assert result.lines_changed > 0

    def test_returns_none_for_unknown_type(self, tmp_path):
        opp = _make_opp("nonexistent_type", "src/file.ts:1")
        result = generate_patch(opp, tmp_path)
        assert result is None

    def test_returns_none_for_missing_file(self, tmp_path):
        opp = _make_opp("set_membership", "src/nonexistent.ts:1")
        result = generate_patch(opp, tmp_path)
        assert result is None

    def test_returns_none_when_template_cannot_apply(self, tmp_path):
        source_file = tmp_path / "utils.ts"
        source_file.write_text('const x = arr.indexOf(item);\n')

        opp = _make_opp("set_membership", "utils.ts:1")
        result = generate_patch(opp, tmp_path)
        assert result is None

    def test_diff_is_valid_unified_format(self, tmp_path):
        source_file = tmp_path / "utils.ts"
        source_file.write_text('if (arr.indexOf(x) !== -1) { return true; }\n')

        opp = _make_opp("set_membership", "utils.ts:1")
        result = generate_patch(opp, tmp_path)

        assert result is not None
        assert "--- a/utils.ts" in result.diff
        assert "+++ b/utils.ts" in result.diff

    def test_patch_result_has_all_fields(self, tmp_path):
        source_file = tmp_path / "utils.ts"
        source_file.write_text('if (arr.indexOf(x) !== -1) { return true; }\n')

        opp = _make_opp("set_membership", "utils.ts:1")
        result = generate_patch(opp, tmp_path)

        assert result is not None
        assert result.diff
        assert result.explanation
        assert result.touched_files
        assert result.template_name
        assert result.lines_changed >= 0

    def test_to_dict_is_serializable(self, tmp_path):
        source_file = tmp_path / "utils.ts"
        source_file.write_text('if (arr.indexOf(x) !== -1) { return true; }\n')

        opp = _make_opp("set_membership", "utils.ts:1")
        result = generate_patch(opp, tmp_path)

        assert result is not None
        d = result.to_dict()
        assert isinstance(d, dict)
        assert all(k in d for k in ["diff", "explanation", "touched_files", "template_name", "lines_changed"])


class TestConstraintEnforcement:
    def test_too_many_files_raises(self, tmp_path):
        source_file = tmp_path / "utils.ts"
        source_file.write_text('if (arr.indexOf(x) !== -1) {}\n')

        opp = _make_opp("set_membership", "utils.ts:1")

        with patch("runner.patchgen.generator.enforce_constraints") as mock_enforce:
            mock_enforce.side_effect = ConstraintViolation("max_files", "too many files")
            with pytest.raises(ConstraintViolation) as exc:
                generate_patch(opp, tmp_path)
            assert exc.value.constraint == "max_files"


class TestPatchResultType:
    def test_constraint_violation_str(self):
        cv = ConstraintViolation("max_lines", "202 > 200")
        assert "max_lines" in str(cv)
        assert "202 > 200" in str(cv)
        assert cv.constraint == "max_lines"
        assert cv.detail == "202 > 200"
