"""Unit tests for the package.json parser.

Tests parsing logic, framework detection, and package manager detection
using minimal in-memory fixtures.
"""

import json
from pathlib import Path

import pytest

from runner.detector.package_json import (
    detect_framework,
    detect_package_manager,
    get_install_command,
    parse_package_json,
)


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a minimal temp repo directory."""
    return tmp_path


def _write_pkg(tmp_repo: Path, data: dict) -> None:
    (tmp_repo / "package.json").write_text(json.dumps(data))


class TestParsePackageJson:
    def test_extracts_build_script(self, tmp_repo):
        _write_pkg(tmp_repo, {"scripts": {"build": "tsc"}})
        signals = parse_package_json(tmp_repo)
        assert "build" in signals
        assert signals["build"][0].command.endswith("run build")

    def test_extracts_test_script(self, tmp_repo):
        _write_pkg(tmp_repo, {"scripts": {"test": "jest"}})
        signals = parse_package_json(tmp_repo)
        assert "test" in signals

    def test_extracts_typecheck_script(self, tmp_repo):
        _write_pkg(tmp_repo, {"scripts": {"typecheck": "tsc --noEmit"}})
        signals = parse_package_json(tmp_repo)
        assert "typecheck" in signals

    def test_no_scripts_returns_empty(self, tmp_repo):
        _write_pkg(tmp_repo, {"name": "no-scripts"})
        signals = parse_package_json(tmp_repo)
        assert signals == {}

    def test_no_package_json_returns_empty(self, tmp_repo):
        signals = parse_package_json(tmp_repo)
        assert signals == {}

    def test_invalid_json_returns_empty(self, tmp_repo):
        (tmp_repo / "package.json").write_text("not json {{")
        signals = parse_package_json(tmp_repo)
        assert signals == {}

    def test_multiple_matching_scripts_in_category(self, tmp_repo):
        _write_pkg(tmp_repo, {"scripts": {"build": "tsc", "compile": "babel"}})
        signals = parse_package_json(tmp_repo)
        assert len(signals["build"]) == 2

    def test_confidence_is_0_9(self, tmp_repo):
        _write_pkg(tmp_repo, {"scripts": {"test": "jest"}})
        signals = parse_package_json(tmp_repo)
        assert signals["test"][0].confidence == 0.9


class TestDetectFramework:
    def test_nextjs(self, tmp_repo):
        _write_pkg(tmp_repo, {"dependencies": {"next": "15.0.0", "react": "19.0.0"}})
        fw = detect_framework(tmp_repo)
        assert fw is not None
        assert fw.command == "nextjs"

    def test_nestjs(self, tmp_repo):
        _write_pkg(tmp_repo, {"dependencies": {"@nestjs/core": "10.0.0"}})
        fw = detect_framework(tmp_repo)
        assert fw.command == "nestjs"

    def test_express(self, tmp_repo):
        _write_pkg(tmp_repo, {"dependencies": {"express": "4.0.0"}})
        fw = detect_framework(tmp_repo)
        assert fw.command == "express"

    def test_react_only(self, tmp_repo):
        _write_pkg(tmp_repo, {"dependencies": {"react": "19.0.0"}})
        fw = detect_framework(tmp_repo)
        assert fw.command == "react"

    def test_vite_in_dev_deps(self, tmp_repo):
        _write_pkg(tmp_repo, {
            "dependencies": {"react": "19.0.0"},
            "devDependencies": {"vite": "6.0.0"},
        })
        fw = detect_framework(tmp_repo)
        assert fw.command == "react-vite"

    def test_no_known_framework(self, tmp_repo):
        _write_pkg(tmp_repo, {"dependencies": {"lodash": "4.0.0"}})
        fw = detect_framework(tmp_repo)
        assert fw is None

    def test_no_package_json(self, tmp_repo):
        fw = detect_framework(tmp_repo)
        assert fw is None


class TestDetectPackageManager:
    def test_npm_from_lock(self, tmp_repo):
        _write_pkg(tmp_repo, {})
        (tmp_repo / "package-lock.json").write_text("{}")
        pm = detect_package_manager(tmp_repo)
        assert pm.command == "npm"
        assert pm.confidence == 0.95

    def test_yarn_from_lock(self, tmp_repo):
        _write_pkg(tmp_repo, {})
        (tmp_repo / "yarn.lock").write_text("")
        pm = detect_package_manager(tmp_repo)
        assert pm.command == "yarn"

    def test_pnpm_from_lock(self, tmp_repo):
        _write_pkg(tmp_repo, {})
        (tmp_repo / "pnpm-lock.yaml").write_text("")
        pm = detect_package_manager(tmp_repo)
        assert pm.command == "pnpm"

    def test_bun_from_lock(self, tmp_repo):
        _write_pkg(tmp_repo, {})
        (tmp_repo / "bun.lockb").write_text("")
        pm = detect_package_manager(tmp_repo)
        assert pm.command == "bun"

    def test_pnpm_lock_wins_over_npm_lock(self, tmp_repo):
        """pnpm-lock.yaml has higher priority than package-lock.json."""
        _write_pkg(tmp_repo, {})
        (tmp_repo / "pnpm-lock.yaml").write_text("")
        (tmp_repo / "package-lock.json").write_text("{}")
        pm = detect_package_manager(tmp_repo)
        assert pm.command == "pnpm"

    def test_package_manager_field(self, tmp_repo):
        _write_pkg(tmp_repo, {"packageManager": "pnpm@8.0.0"})
        pm = detect_package_manager(tmp_repo)
        assert pm.command == "pnpm"
        assert pm.confidence == 0.9

    def test_no_lock_file_defaults_npm(self, tmp_repo):
        _write_pkg(tmp_repo, {})
        pm = detect_package_manager(tmp_repo)
        assert pm.command == "npm"
        assert pm.confidence == 0.5

    def test_no_package_json_fallback(self, tmp_repo):
        pm = detect_package_manager(tmp_repo)
        assert pm.command == "npm"
        assert pm.confidence == 0.1


class TestGetInstallCommand:
    def test_npm(self):
        assert get_install_command("npm") == "npm ci"

    def test_yarn(self):
        assert "yarn" in get_install_command("yarn")
        assert "frozen-lockfile" in get_install_command("yarn")

    def test_pnpm(self):
        assert "pnpm" in get_install_command("pnpm")
        assert "frozen-lockfile" in get_install_command("pnpm")

    def test_bun(self):
        assert "bun" in get_install_command("bun")

    def test_unknown_fallback(self):
        assert get_install_command("unknown") == "npm ci"
