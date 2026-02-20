"""Golden tests for end-to-end detection on fixture repos.

Each fixture mimics a real-world repo structure. The detector should
produce the expected package manager, framework, and commands.
"""

from pathlib import Path

import pytest

from runner.detector import detect

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "repos"


class TestNextjsFixture:
    """Detection results for a Next.js app with npm and vitest."""

    @pytest.fixture
    def result(self):
        return detect(FIXTURES_DIR / "nextjs-app")

    def test_package_manager(self, result):
        assert result.package_manager == "npm"

    def test_install_cmd(self, result):
        assert result.install_cmd == "npm ci"

    def test_build_cmd(self, result):
        assert "build" in result.build_cmd

    def test_test_cmd(self, result):
        assert "test" in result.test_cmd

    def test_typecheck_cmd(self, result):
        assert result.typecheck_cmd is not None
        assert "typecheck" in result.typecheck_cmd

    def test_framework(self, result):
        assert result.framework == "nextjs"

    def test_confidence_above_threshold(self, result):
        assert result.confidence >= 0.5

    def test_evidence_is_populated(self, result):
        assert len(result.evidence) >= 4

    def test_to_dict_has_all_keys(self, result):
        d = result.to_dict()
        expected_keys = {
            "package_manager", "install_cmd", "build_cmd",
            "test_cmd", "typecheck_cmd", "bench_cmd", "framework",
            "language", "confidence", "evidence",
        }
        assert set(d.keys()) == expected_keys


class TestNestjsFixture:
    """Detection results for a NestJS API with pnpm and jest."""

    @pytest.fixture
    def result(self):
        return detect(FIXTURES_DIR / "nestjs-api")

    def test_package_manager(self, result):
        assert result.package_manager == "pnpm"

    def test_install_cmd(self, result):
        assert "pnpm" in result.install_cmd
        assert "frozen-lockfile" in result.install_cmd

    def test_build_cmd(self, result):
        assert "build" in result.build_cmd

    def test_test_cmd(self, result):
        assert "test" in result.test_cmd

    def test_framework(self, result):
        assert result.framework == "nestjs"

    def test_confidence_above_threshold(self, result):
        assert result.confidence >= 0.5


class TestExpressFixture:
    """Detection results for an Express server with yarn and mocha."""

    @pytest.fixture
    def result(self):
        return detect(FIXTURES_DIR / "express-server")

    def test_package_manager(self, result):
        assert result.package_manager == "yarn"

    def test_install_cmd(self, result):
        assert "yarn" in result.install_cmd
        assert "frozen-lockfile" in result.install_cmd

    def test_test_cmd(self, result):
        assert "test" in result.test_cmd

    def test_framework(self, result):
        assert result.framework == "express"

    def test_no_typecheck(self, result):
        """Express fixture has no typecheck script."""
        assert result.typecheck_cmd is None

    def test_confidence_above_threshold(self, result):
        assert result.confidence >= 0.5


class TestReactViteFixture:
    """Detection results for a React Vite app with npm and vitest."""

    @pytest.fixture
    def result(self):
        return detect(FIXTURES_DIR / "react-vite")

    def test_package_manager(self, result):
        assert result.package_manager == "npm"

    def test_install_cmd(self, result):
        assert result.install_cmd == "npm ci"

    def test_build_cmd(self, result):
        assert "build" in result.build_cmd

    def test_test_cmd(self, result):
        assert "test" in result.test_cmd

    def test_framework(self, result):
        # Vite is detected since it appears before react in the indicator list
        assert result.framework == "react-vite"

    def test_confidence_above_threshold(self, result):
        assert result.confidence >= 0.5
