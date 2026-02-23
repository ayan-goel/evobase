"""Tests for the patch applicator (apply/revert unified diffs)."""

import difflib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from runner.validator.patch_applicator import (
    PatchApplyError,
    apply_diff,
    check_patch_available,
    revert_diff,
)


def _make_diff(original: str, modified: str, filename: str = "file.ts") -> str:
    """Helper to produce a unified diff from two strings.

    Uses keepends=True so content lines carry their own newlines, and
    lineterm='\\n' so header lines (--- / +++ / @@) are also terminated.
    This matches the format expected by `patch -p1`.
    """
    lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="\n",
    )
    return "".join(lines)


class TestApplyDiff:
    def test_applies_simple_diff(self, tmp_path):
        src_file = tmp_path / "file.ts"
        original = 'if (arr.indexOf(x) !== -1) { return true; }\n'
        modified = 'if (arr.includes(x)) { return true; }\n'
        src_file.write_text(original)

        diff = _make_diff(original, modified)
        apply_diff(tmp_path, diff)

        assert src_file.read_text() == modified

    def test_raises_on_empty_diff(self, tmp_path):
        with pytest.raises(PatchApplyError, match="Empty diff"):
            apply_diff(tmp_path, "")

    def test_raises_on_whitespace_only_diff(self, tmp_path):
        with pytest.raises(PatchApplyError, match="Empty diff"):
            apply_diff(tmp_path, "   \n  \n")

    def test_raises_when_patch_binary_missing(self, tmp_path):
        diff = _make_diff("old\n", "new\n")
        with patch("runner.validator.patch_applicator.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("patch not found")
            with pytest.raises(PatchApplyError, match="patch binary not found"):
                apply_diff(tmp_path, diff)

    def test_raises_on_nonzero_exit_code(self, tmp_path):
        diff = _make_diff("old\n", "new\n")
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "hunk FAILED"

        with patch("runner.validator.patch_applicator.subprocess.run", return_value=mock_result):
            with pytest.raises(PatchApplyError, match="patch failed"):
                apply_diff(tmp_path, diff)


class TestRevertDiff:
    def test_reverts_applied_diff(self, tmp_path):
        src_file = tmp_path / "file.ts"
        original = 'if (arr.indexOf(x) !== -1) { return true; }\n'
        modified = 'if (arr.includes(x)) { return true; }\n'

        diff = _make_diff(original, modified)

        # Apply first
        src_file.write_text(original)
        apply_diff(tmp_path, diff)
        assert src_file.read_text() == modified

        # Revert
        revert_diff(tmp_path, diff)
        assert src_file.read_text() == original

    def test_raises_on_empty_diff(self, tmp_path):
        with pytest.raises(PatchApplyError, match="Empty diff"):
            revert_diff(tmp_path, "")

    def test_raises_when_patch_binary_missing(self, tmp_path):
        diff = _make_diff("old\n", "new\n")
        with patch("runner.validator.patch_applicator.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("patch not found")
            with pytest.raises(PatchApplyError, match="patch binary not found"):
                revert_diff(tmp_path, diff)

    def test_raises_on_nonzero_exit_code(self, tmp_path):
        diff = _make_diff("old\n", "new\n")
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "hunk FAILED"

        with patch("runner.validator.patch_applicator.subprocess.run", return_value=mock_result):
            with pytest.raises(PatchApplyError, match="patch revert failed"):
                revert_diff(tmp_path, diff)


class TestFuzzFactor:
    """Verify the fuzz flag is included so LLM-generated diffs with slightly
    off context lines are still accepted by patch."""

    def test_apply_includes_fuzz_flag(self, tmp_path):
        diff = _make_diff("old\n", "new\n")
        captured: list[list[str]] = []

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch(
            "runner.validator.patch_applicator.subprocess.run",
            side_effect=lambda cmd, **_: captured.append(cmd) or mock_result,
        ):
            apply_diff(tmp_path, diff)

        assert captured, "subprocess.run was not called"
        assert "--fuzz=3" in captured[0], f"--fuzz=3 missing from cmd: {captured[0]}"

    def test_revert_includes_fuzz_flag(self, tmp_path):
        diff = _make_diff("old\n", "new\n")
        captured: list[list[str]] = []

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch(
            "runner.validator.patch_applicator.subprocess.run",
            side_effect=lambda cmd, **_: captured.append(cmd) or mock_result,
        ):
            revert_diff(tmp_path, diff)

        assert captured, "subprocess.run was not called"
        assert "--fuzz=3" in captured[0], f"--fuzz=3 missing from cmd: {captured[0]}"


class TestCheckPatchAvailable:
    def test_returns_true_when_available(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("runner.validator.patch_applicator.subprocess.run", return_value=mock_result):
            assert check_patch_available() is True

    def test_returns_false_when_not_found(self):
        with patch("runner.validator.patch_applicator.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            assert check_patch_available() is False

    def test_returns_false_on_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("runner.validator.patch_applicator.subprocess.run", return_value=mock_result):
            assert check_patch_available() is False
