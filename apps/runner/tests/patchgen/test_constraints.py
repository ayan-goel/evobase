"""Tests for hard constraint enforcement."""

import pytest

from runner.patchgen.constraints import (
    MAX_FILES,
    MAX_LINES_CHANGED,
    count_diff_lines,
    enforce_constraints,
    is_forbidden_file,
)
from runner.patchgen.types import ConstraintViolation, PatchResult


def _make_patch(**kwargs) -> PatchResult:
    defaults = {
        "diff": "--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n",
        "explanation": "test",
        "touched_files": ["src/utils.ts"],
        "template_name": "test",
        "lines_changed": 2,
    }
    defaults.update(kwargs)
    return PatchResult(**defaults)


class TestFileCountConstraint:
    def test_one_file_passes(self):
        patch = _make_patch(touched_files=["src/a.ts"])
        enforce_constraints(patch)  # Should not raise

    def test_five_files_passes(self):
        patch = _make_patch(touched_files=[f"src/file{i}.ts" for i in range(5)])
        enforce_constraints(patch)

    def test_six_files_raises(self):
        patch = _make_patch(touched_files=[f"src/file{i}.ts" for i in range(6)])
        with pytest.raises(ConstraintViolation) as exc:
            enforce_constraints(patch)
        assert exc.value.constraint == "max_files"

    def test_zero_files_passes(self):
        patch = _make_patch(touched_files=[])
        enforce_constraints(patch)


class TestLineCountConstraint:
    def test_small_diff_passes(self):
        diff = "--- a\n+++ b\n@@ -1,5 +1,5 @@\n" + "-old\n" * 5 + "+new\n" * 5
        patch = _make_patch(diff=diff, lines_changed=10)
        enforce_constraints(patch)

    def test_exactly_200_passes(self):
        diff = "-old\n" * 100 + "+new\n" * 100
        patch = _make_patch(diff=diff, lines_changed=200)
        enforce_constraints(patch)

    def test_201_lines_raises(self):
        diff = "-old\n" * 101 + "+new\n" * 101
        patch = _make_patch(diff=diff, lines_changed=202)
        with pytest.raises(ConstraintViolation) as exc:
            enforce_constraints(patch)
        assert exc.value.constraint == "max_lines"


class TestForbiddenFileConstraint:
    @pytest.mark.parametrize("path", [
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        ".env",
        ".env.local",
        "tsconfig.json",
        "jest.config.ts",
        "vitest.config.ts",
        "vite.config.ts",
        "next.config.js",
        "src/app.test.ts",
        "src/utils.spec.ts",
        "__tests__/helper.ts",
        "test/integration.ts",
    ])
    def test_forbidden_file_raises(self, path):
        patch = _make_patch(touched_files=[path])
        with pytest.raises(ConstraintViolation) as exc:
            enforce_constraints(patch)
        assert exc.value.constraint == "forbidden_file"

    @pytest.mark.parametrize("path", [
        "src/utils.ts",
        "src/components/Button.tsx",
        "lib/helpers.js",
        "app/api/route.ts",
    ])
    def test_allowed_file_passes(self, path):
        patch = _make_patch(touched_files=[path])
        enforce_constraints(patch)


class TestCountDiffLines:
    def test_counts_additions_and_deletions(self):
        diff = "--- a\n+++ b\n@@ -1,2 +1,2 @@\n-old1\n-old2\n+new1\n+new2\n"
        assert count_diff_lines(diff) == 4

    def test_ignores_headers(self):
        diff = "--- a/file.ts\n+++ b/file.ts\n@@ -1 +1 @@\n-x\n+y\n"
        assert count_diff_lines(diff) == 2

    def test_ignores_context_lines(self):
        diff = " context\n-old\n+new\n context\n"
        assert count_diff_lines(diff) == 2

    def test_empty_diff(self):
        assert count_diff_lines("") == 0


class TestIsForbiddenFile:
    def test_package_json_is_forbidden(self):
        assert is_forbidden_file("package.json") is True

    def test_test_file_is_forbidden(self):
        assert is_forbidden_file("utils.test.ts") is True

    def test_source_file_is_not_forbidden(self):
        assert is_forbidden_file("src/utils.ts") is False
