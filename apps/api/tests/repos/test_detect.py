"""Tests for the inline framework detection module.

All tests here are pure-function (no network calls). The functions under test
are _detect_from_files, _detect_rust, _detect_go, _detect_python, _detect_js,
and the TTL cache in detect_repo_framework.
"""

import json
import time
import unittest.mock as mock

import pytest

from app.repos.detect import (
    _detect_from_files,
    _detect_go,
    _detect_js,
    _detect_python,
    _detect_rust,
    detect_repo_framework,
    _CACHE,
    _TTL_SECONDS,
)
from app.repos.schemas import DetectFrameworkResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pkg_json(deps: dict, dev_deps: dict | None = None, lock: str | None = None) -> dict[str, bytes]:
    payload = {"dependencies": deps}
    if dev_deps:
        payload["devDependencies"] = dev_deps
    files: dict[str, bytes] = {"package.json": json.dumps(payload).encode()}
    if lock:
        files[lock] = b""
    return files


def _cargo(deps: list[str]) -> bytes:
    lines = ["[dependencies]"] + [f'{d} = "1.0"' for d in deps]
    return "\n".join(lines).encode()


def _gomod(requires: list[str]) -> bytes:
    lines = ["module example.com/app", "", "require ("]
    for r in requires:
        lines.append(f"\t{r} v1.0.0")
    lines.append(")")
    return "\n".join(lines).encode()


def _pyproject(deps: list[str]) -> bytes:
    dep_lines = ", ".join(f'"{d}"' for d in deps)
    return f"""
[project]
name = "myapp"
dependencies = [{dep_lines}]
""".encode()


def _requirements(deps: list[str]) -> bytes:
    return "\n".join(deps).encode()


# ---------------------------------------------------------------------------
# Rust detection
# ---------------------------------------------------------------------------

class TestDetectRust:
    def test_axum_from_cargo_toml(self):
        result = _detect_rust(_cargo(["axum", "tokio"]))
        assert result.framework == "axum"
        assert result.language == "rust"
        assert result.package_manager == "cargo"
        assert result.confidence >= 0.9

    def test_actix_from_cargo_toml(self):
        result = _detect_rust(_cargo(["actix-web"]))
        assert result.framework == "actix"

    def test_rocket_from_cargo_toml(self):
        result = _detect_rust(_cargo(["rocket"]))
        assert result.framework == "rocket"

    def test_warp_from_cargo_toml(self):
        result = _detect_rust(_cargo(["warp"]))
        assert result.framework == "warp"

    def test_no_framework_falls_back_to_rust_generic(self):
        result = _detect_rust(_cargo(["serde", "tokio"]))
        assert result.language == "rust"
        assert result.framework == "rust"
        assert result.confidence >= 0.5

    def test_invalid_toml_returns_partial_result(self):
        result = _detect_rust(b"[dependencies\nnot valid")
        assert result.language == "rust"
        assert result.package_manager == "cargo"


# ---------------------------------------------------------------------------
# Go detection
# ---------------------------------------------------------------------------

class TestDetectGo:
    def test_gin_from_gomod(self):
        result = _detect_go(_gomod(["github.com/gin-gonic/gin"]))
        assert result.framework == "gin"
        assert result.language == "go"
        assert result.package_manager == "go"

    def test_echo_from_gomod(self):
        result = _detect_go(_gomod(["github.com/labstack/echo/v4"]))
        assert result.framework == "echo"

    def test_fiber_from_gomod(self):
        result = _detect_go(_gomod(["github.com/gofiber/fiber/v2"]))
        assert result.framework == "fiber"

    def test_chi_from_gomod(self):
        result = _detect_go(_gomod(["github.com/go-chi/chi/v5"]))
        assert result.framework == "chi"

    def test_gorilla_from_gomod(self):
        result = _detect_go(_gomod(["github.com/gorilla/mux"]))
        assert result.framework == "gorilla"

    def test_no_framework_falls_back_to_go_generic(self):
        result = _detect_go(_gomod(["github.com/some/lib"]))
        assert result.language == "go"
        assert result.framework == "go"


# ---------------------------------------------------------------------------
# Python detection
# ---------------------------------------------------------------------------

class TestDetectPython:
    def test_fastapi_from_pyproject(self):
        files = {"pyproject.toml": _pyproject(["fastapi>=0.100", "uvicorn"])}
        result = _detect_python(files)
        assert result.framework == "fastapi"
        assert result.language == "python"

    def test_django_from_requirements_txt(self):
        files = {"requirements.txt": _requirements(["Django>=4.0", "gunicorn"])}
        result = _detect_python(files)
        assert result.framework == "django"
        assert result.language == "python"

    def test_flask_from_requirements_txt(self):
        files = {"requirements.txt": _requirements(["flask", "werkzeug"])}
        result = _detect_python(files)
        assert result.framework == "flask"

    def test_no_framework_still_returns_python(self):
        files = {"requirements.txt": _requirements(["requests", "boto3"])}
        result = _detect_python(files)
        assert result.language == "python"
        assert result.framework is None

    def test_uv_lock_sets_pm_to_uv(self):
        files = {
            "pyproject.toml": _pyproject(["fastapi"]),
            "uv.lock": b"",
        }
        result = _detect_python(files)
        assert result.package_manager == "uv"

    def test_poetry_lock_sets_pm_to_poetry(self):
        files = {
            "pyproject.toml": _pyproject(["django"]),
            "poetry.lock": b"",
        }
        result = _detect_python(files)
        assert result.package_manager == "poetry"

    def test_no_lock_file_defaults_to_pip(self):
        files = {"requirements.txt": _requirements(["flask"])}
        result = _detect_python(files)
        assert result.package_manager == "pip"


# ---------------------------------------------------------------------------
# JavaScript / TypeScript detection
# ---------------------------------------------------------------------------

class TestDetectJs:
    def test_nextjs_from_package_json(self):
        files = _pkg_json({"next": "14.0.0", "react": "18.0.0"})
        result = _detect_js(files)
        assert result.framework == "nextjs"
        assert result.language == "javascript"

    def test_react_vite_from_package_json(self):
        files = _pkg_json({"react": "18.0.0"}, dev_deps={"vite": "5.0.0"})
        result = _detect_js(files)
        assert result.framework == "react-vite"

    def test_express_from_package_json(self):
        files = _pkg_json({"express": "4.0.0"})
        result = _detect_js(files)
        assert result.framework == "express"

    def test_pnpm_lock_sets_pm_to_pnpm(self):
        files = _pkg_json({"next": "14.0.0"}, lock="pnpm-lock.yaml")
        result = _detect_js(files)
        assert result.package_manager == "pnpm"

    def test_yarn_lock_sets_pm_to_yarn(self):
        files = _pkg_json({"react": "18.0.0"}, lock="yarn.lock")
        result = _detect_js(files)
        assert result.package_manager == "yarn"

    def test_no_known_framework_returns_javascript(self):
        files = _pkg_json({"lodash": "4.0.0"})
        result = _detect_js(files)
        assert result.language == "javascript"
        assert result.framework is None


# ---------------------------------------------------------------------------
# Priority order (Rust > Go > Python > JS)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Ruby detection (inline API detector)
# ---------------------------------------------------------------------------

class TestDetectRuby:
    def test_rails_from_gemfile(self):
        gemfile = b"source 'https://rubygems.org'\ngem 'rails', '~> 7.1'\n"
        result = _detect_from_files({"Gemfile": gemfile})
        assert result.framework == "rails"
        assert result.language == "ruby"
        assert result.package_manager == "bundler"

    def test_sinatra_from_gemfile(self):
        gemfile = b"source 'https://rubygems.org'\ngem 'sinatra'\n"
        result = _detect_from_files({"Gemfile": gemfile})
        assert result.framework == "sinatra"

    def test_no_framework_gem_returns_ruby_generic(self):
        gemfile = b"source 'https://rubygems.org'\ngem 'json'\n"
        result = _detect_from_files({"Gemfile": gemfile})
        assert result.language == "ruby"
        assert result.framework == "ruby"


# ---------------------------------------------------------------------------
# JVM detection (inline API detector)
# ---------------------------------------------------------------------------

_SPRING_POM = b"""<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.0</version>
  </parent>
  <groupId>com.example</groupId>
  <artifactId>myapp</artifactId>
</project>
"""

_SPRING_GRADLE = b"""
plugins {
    id 'org.springframework.boot' version '3.2.0'
    id 'java'
}
"""

_QUARKUS_POM = b"""<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <dependencyManagement>
    <dependencies>
      <dependency>
        <artifactId>quarkus-bom</artifactId>
      </dependency>
    </dependencies>
  </dependencyManagement>
</project>
"""


class TestDetectJVM:
    def test_spring_boot_from_pom(self):
        result = _detect_from_files({"pom.xml": _SPRING_POM})
        assert result.framework == "spring-boot"
        assert result.language == "java"
        assert result.package_manager == "maven"

    def test_spring_boot_from_gradle(self):
        result = _detect_from_files({"build.gradle": _SPRING_GRADLE})
        assert result.framework == "spring-boot"
        assert result.language == "java"
        assert result.package_manager == "gradle"

    def test_quarkus_from_pom(self):
        result = _detect_from_files({"pom.xml": _QUARKUS_POM})
        assert result.framework == "quarkus"

    def test_minimal_pom_returns_java_generic(self):
        pom = b"<?xml version='1.0'?><project><artifactId>plain</artifactId></project>"
        result = _detect_from_files({"pom.xml": pom})
        assert result.language == "java"
        assert result.framework == "java"

    def test_pom_wins_over_package_json(self):
        files = {
            "pom.xml": _SPRING_POM,
            "package.json": b'{"dependencies": {"next": "14.0.0"}}',
        }
        result = _detect_from_files(files)
        assert result.language == "java"

    def test_ruby_wins_over_jvm(self):
        files = {
            "Gemfile": b"source 'https://rubygems.org'\ngem 'rails'\n",
            "pom.xml": _SPRING_POM,
        }
        result = _detect_from_files(files)
        assert result.language == "ruby"


class TestPriorityOrder:
    def test_cargo_toml_wins_over_package_json(self):
        files: dict[str, bytes] = {
            "Cargo.toml": _cargo(["axum"]),
            "package.json": json.dumps({"dependencies": {"next": "14.0.0"}}).encode(),
        }
        result = _detect_from_files(files)
        assert result.language == "rust"
        assert result.framework == "axum"

    def test_go_mod_wins_over_package_json(self):
        files: dict[str, bytes] = {
            "go.mod": _gomod(["github.com/gin-gonic/gin"]),
            "package.json": json.dumps({"dependencies": {"next": "14.0.0"}}).encode(),
        }
        result = _detect_from_files(files)
        assert result.language == "go"

    def test_no_manifest_returns_zero_confidence(self):
        result = _detect_from_files({})
        assert result.confidence == 0.0
        assert result.framework is None
        assert result.language is None


# ---------------------------------------------------------------------------
# TTL cache
# ---------------------------------------------------------------------------

class TestTTLCache:
    def test_cache_hit_returns_same_object(self):
        """Second call with the same key skips the async function and returns cached object."""
        sentinel = DetectFrameworkResponse(framework="nextjs", language="javascript", confidence=0.9)
        key = "9999:owner/cached-repo:"

        # Inject entry with far-future expiry
        _CACHE[key] = (sentinel, time.monotonic() + _TTL_SECONDS)

        async def _fake_probe(*_a, **_kw):
            raise AssertionError("probe should not be called on cache hit")

        import asyncio
        import app.repos.detect as detect_mod

        original = detect_mod._probe_files
        detect_mod._probe_files = _fake_probe
        try:
            result = asyncio.run(
                detect_repo_framework("tok", 9999, "owner/cached-repo", None)
            )
        finally:
            detect_mod._probe_files = original
            del _CACHE[key]

        assert result is sentinel

    def test_expired_cache_is_not_used(self):
        """Entry with an already-expired monotonic timestamp triggers a fresh fetch."""
        old = DetectFrameworkResponse(framework="old", language="rust", confidence=0.9)
        key = "8888:owner/stale-repo:"
        # Expired 1 second ago
        _CACHE[key] = (old, time.monotonic() - 1.0)

        async def _fake_probe(*_a, **_kw):
            return {"go.mod": _gomod(["github.com/gin-gonic/gin"])}

        import asyncio
        import app.repos.detect as detect_mod

        original = detect_mod._probe_files
        detect_mod._probe_files = _fake_probe
        try:
            result = asyncio.run(
                detect_repo_framework("tok", 8888, "owner/stale-repo", None)
            )
        finally:
            detect_mod._probe_files = original
            del _CACHE[key]

        assert result.language == "go"
        assert result.framework == "gin"
