"""Tests for the Go ecosystem detector.

All tests use in-memory fixtures written to tmp_path — no real repos cloned.
"""

from pathlib import Path

import pytest

from runner.detector.go import detect_go
from runner.detector.orchestrator import detect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gomod(tmp_path: Path, content: str) -> Path:
    (tmp_path / "go.mod").write_text(content, encoding="utf-8")
    return tmp_path


MINIMAL_GOMOD = """\
module github.com/example/myapp

go 1.23
"""

MULTILINE_REQUIRE = """\
module github.com/example/myapp

go 1.23

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/joho/godotenv v1.5.1 // indirect
)
"""

SINGLE_LINE_REQUIRE = """\
module github.com/example/myapp

go 1.23

require github.com/labstack/echo/v4 v4.12.0
"""


# ---------------------------------------------------------------------------
# Framework detection
# ---------------------------------------------------------------------------

class TestGoFrameworkDetection:
    def test_gin_detected_from_gomod(self, tmp_path):
        _gomod(tmp_path, MULTILINE_REQUIRE)
        result = detect_go(tmp_path)
        assert result.framework == "gin"
        assert result.language == "go"

    def test_echo_detected_from_single_line_require(self, tmp_path):
        _gomod(tmp_path, SINGLE_LINE_REQUIRE)
        result = detect_go(tmp_path)
        assert result.framework == "echo"

    def test_fiber_detected_from_gomod(self, tmp_path):
        _gomod(tmp_path, """\
module github.com/example/app
go 1.23
require github.com/gofiber/fiber/v2 v2.52.0
""")
        result = detect_go(tmp_path)
        assert result.framework == "fiber"

    def test_chi_detected_from_gomod(self, tmp_path):
        _gomod(tmp_path, """\
module github.com/example/app
go 1.23
require github.com/go-chi/chi/v5 v5.0.0
""")
        result = detect_go(tmp_path)
        assert result.framework == "chi"

    def test_no_framework_returns_go(self, tmp_path):
        _gomod(tmp_path, MINIMAL_GOMOD)
        result = detect_go(tmp_path)
        assert result.framework == "go"
        assert result.language == "go"

    def test_multiline_require_block_parsed(self, tmp_path):
        """Multi-line require (...) blocks must be fully parsed."""
        content = """\
module github.com/example/app
go 1.23
require (
    golang.org/x/net v0.20.0
    github.com/gorilla/mux v1.8.1
    github.com/joho/godotenv v1.5.1
)
"""
        _gomod(tmp_path, content)
        result = detect_go(tmp_path)
        assert result.framework == "gorilla"


# ---------------------------------------------------------------------------
# Default commands
# ---------------------------------------------------------------------------

class TestGoDefaultCommands:
    def test_go_mod_download_install_cmd(self, tmp_path):
        _gomod(tmp_path, MINIMAL_GOMOD)
        result = detect_go(tmp_path)
        assert result.install_cmd == "go mod download"

    def test_go_build_default(self, tmp_path):
        _gomod(tmp_path, MINIMAL_GOMOD)
        result = detect_go(tmp_path)
        assert result.build_cmd == "go build ./..."

    def test_go_test_default_test_cmd(self, tmp_path):
        _gomod(tmp_path, MINIMAL_GOMOD)
        result = detect_go(tmp_path)
        assert result.test_cmd == "go test ./..."

    def test_go_vet_typecheck_cmd(self, tmp_path):
        _gomod(tmp_path, MINIMAL_GOMOD)
        result = detect_go(tmp_path)
        assert result.typecheck_cmd == "go vet ./..."

    def test_package_manager_is_go(self, tmp_path):
        _gomod(tmp_path, MINIMAL_GOMOD)
        result = detect_go(tmp_path)
        assert result.package_manager == "go"


# ---------------------------------------------------------------------------
# Language field and orchestrator routing
# ---------------------------------------------------------------------------

class TestGoLanguageAndRouting:
    def test_language_is_go(self, tmp_path):
        _gomod(tmp_path, MINIMAL_GOMOD)
        result = detect_go(tmp_path)
        assert result.language == "go"

    def test_orchestrator_routes_to_go_on_gomod(self, tmp_path):
        _gomod(tmp_path, MULTILINE_REQUIRE)
        result = detect(tmp_path)
        assert result.language == "go"
        assert result.framework == "gin"

    def test_language_in_to_dict(self, tmp_path):
        _gomod(tmp_path, MINIMAL_GOMOD)
        result = detect_go(tmp_path)
        assert result.to_dict()["language"] == "go"

    def test_cargo_takes_priority_over_gomod(self, tmp_path):
        """When both Cargo.toml and go.mod are present, Rust wins (higher priority)."""
        _gomod(tmp_path, MINIMAL_GOMOD)
        (tmp_path / "Cargo.toml").write_text(
            '[package]\nname = "app"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        result = detect(tmp_path)
        assert result.language == "rust"
