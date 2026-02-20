"""Tests for the Rust ecosystem detector.

All tests use in-memory fixtures written to tmp_path — no real repos cloned.
"""

from pathlib import Path

import pytest

from runner.detector.rust import detect_rust
from runner.detector.orchestrator import detect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cargo(tmp_path: Path, content: str) -> Path:
    (tmp_path / "Cargo.toml").write_text(content, encoding="utf-8")
    return tmp_path


MINIMAL_CARGO = """\
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"
"""

AXUM_CARGO = """\
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"

[dependencies]
axum = "0.7"
tokio = { version = "1", features = ["full"] }
"""

ACTIX_CARGO = """\
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"

[dependencies]
actix-web = "4"
"""

ROCKET_CARGO = """\
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"

[dependencies]
rocket = "0.5"
"""

WARP_CARGO = """\
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"

[dependencies]
warp = "0.3"
"""

WORKSPACE_CARGO = """\
[workspace]
members = ["crates/api", "crates/core"]

[workspace.dependencies]
axum = "0.7"
tokio = { version = "1", features = ["full"] }
"""


# ---------------------------------------------------------------------------
# Framework detection
# ---------------------------------------------------------------------------

class TestRustFrameworkDetection:
    def test_axum_detected_from_cargo_toml(self, tmp_path):
        _cargo(tmp_path, AXUM_CARGO)
        result = detect_rust(tmp_path)
        assert result.framework == "axum"
        assert result.language == "rust"

    def test_actix_detected_from_cargo_toml(self, tmp_path):
        _cargo(tmp_path, ACTIX_CARGO)
        result = detect_rust(tmp_path)
        assert result.framework == "actix"

    def test_rocket_detected_from_cargo_toml(self, tmp_path):
        _cargo(tmp_path, ROCKET_CARGO)
        result = detect_rust(tmp_path)
        assert result.framework == "rocket"

    def test_warp_detected_from_cargo_toml(self, tmp_path):
        _cargo(tmp_path, WARP_CARGO)
        result = detect_rust(tmp_path)
        assert result.framework == "warp"

    def test_no_framework_returns_rust(self, tmp_path):
        _cargo(tmp_path, MINIMAL_CARGO)
        result = detect_rust(tmp_path)
        assert result.framework == "rust"
        assert result.language == "rust"

    def test_workspace_cargo_toml_with_dependencies(self, tmp_path):
        """Workspace-level [workspace.dependencies] should be detected."""
        _cargo(tmp_path, WORKSPACE_CARGO)
        result = detect_rust(tmp_path)
        assert result.framework == "axum"

    def test_axum_takes_priority_over_warp(self, tmp_path):
        """Order in FRAMEWORK_INDICATORS: axum before warp."""
        _cargo(tmp_path, """\
[package]
name = "app"
version = "0.1.0"
edition = "2021"

[dependencies]
warp = "0.3"
axum = "0.7"
""")
        result = detect_rust(tmp_path)
        assert result.framework == "axum"


# ---------------------------------------------------------------------------
# Default commands
# ---------------------------------------------------------------------------

class TestRustDefaultCommands:
    def test_cargo_fetch_install_cmd(self, tmp_path):
        _cargo(tmp_path, MINIMAL_CARGO)
        result = detect_rust(tmp_path)
        assert result.install_cmd == "cargo fetch"

    def test_cargo_build_default(self, tmp_path):
        _cargo(tmp_path, MINIMAL_CARGO)
        result = detect_rust(tmp_path)
        assert result.build_cmd == "cargo build"

    def test_cargo_test_default_test_cmd(self, tmp_path):
        _cargo(tmp_path, MINIMAL_CARGO)
        result = detect_rust(tmp_path)
        assert result.test_cmd == "cargo test"

    def test_cargo_check_typecheck_cmd(self, tmp_path):
        _cargo(tmp_path, MINIMAL_CARGO)
        result = detect_rust(tmp_path)
        assert result.typecheck_cmd == "cargo check"

    def test_package_manager_is_cargo(self, tmp_path):
        _cargo(tmp_path, MINIMAL_CARGO)
        result = detect_rust(tmp_path)
        assert result.package_manager == "cargo"


# ---------------------------------------------------------------------------
# Language field and orchestrator routing
# ---------------------------------------------------------------------------

class TestRustLanguageAndRouting:
    def test_language_is_rust(self, tmp_path):
        _cargo(tmp_path, MINIMAL_CARGO)
        result = detect_rust(tmp_path)
        assert result.language == "rust"

    def test_orchestrator_routes_to_rust_on_cargo_toml(self, tmp_path):
        _cargo(tmp_path, AXUM_CARGO)
        result = detect(tmp_path)
        assert result.language == "rust"
        assert result.framework == "axum"

    def test_language_in_to_dict(self, tmp_path):
        _cargo(tmp_path, MINIMAL_CARGO)
        result = detect_rust(tmp_path)
        assert result.to_dict()["language"] == "rust"

    def test_rust_takes_priority_over_python(self, tmp_path):
        """Cargo.toml has highest probe priority — Python files ignored."""
        _cargo(tmp_path, AXUM_CARGO)
        (tmp_path / "requirements.txt").write_text("flask\n", encoding="utf-8")
        result = detect(tmp_path)
        assert result.language == "rust"
        assert result.framework == "axum"
