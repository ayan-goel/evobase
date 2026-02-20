"""Lightweight framework detection via GitHub Contents API.

Fetches only the key manifest files (Cargo.toml, go.mod, pyproject.toml,
requirements.txt, Gemfile, pom.xml, build.gradle, package.json, and lock files)
for a repository and infers the language + framework without cloning the full repo.

Used exclusively by the /repos/detect-framework endpoint to power the
inline badge in the RepoPicker UI. The authoritative detection still runs
inside the Celery worker when a full run is executed.
"""

import asyncio
import json
import re
import time
import tomllib
import xml.etree.ElementTree as ET
from typing import Optional

import httpx

from app.repos.schemas import DetectFrameworkResponse

GITHUB_API_BASE = "https://api.github.com"

# Files to fetch. Order matters for performance — fetch the language-probe
# files first so we can short-circuit on the first match.
_MANIFEST_FILES = [
    "Cargo.toml",
    "go.mod",
    "pyproject.toml",
    "requirements.txt",
    # Ruby
    "Gemfile",
    # JVM
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "package.json",
    # Lock files (package manager signals)
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    "package-lock.json",
]

# TTL cache: key → (DetectFrameworkResponse, expire_monotonic)
_CACHE: dict[str, tuple[DetectFrameworkResponse, float]] = {}
_TTL_SECONDS = 3600  # 1 hour

# Framework indicator tables (same ordering as the runner detector)
_JS_FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    ("next", "nextjs"),
    ("@nestjs/core", "nestjs"),
    ("nuxt", "nuxt"),
    ("gatsby", "gatsby"),
    ("remix", "remix"),
    ("vite", "react-vite"),
    ("@angular/core", "angular"),
    ("svelte", "svelte"),
    ("vue", "vue"),
    ("express", "express"),
    ("fastify", "fastify"),
    ("koa", "koa"),
    ("hapi", "hapi"),
    ("react", "react"),
]

_JS_PM_LOCK_FILES: list[tuple[str, str]] = [
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
]

_PYTHON_FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    ("fastapi", "fastapi"),
    ("django", "django"),
    ("flask", "flask"),
    ("starlette", "starlette"),
    ("aiohttp", "aiohttp"),
    ("tornado", "tornado"),
    ("litestar", "litestar"),
]

_GO_FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    ("gin-gonic/gin", "gin"),
    ("labstack/echo", "echo"),
    ("gofiber/fiber", "fiber"),
    ("go-chi/chi", "chi"),
    ("gorilla/mux", "gorilla"),
]

_RUST_FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    ("axum", "axum"),
    ("actix-web", "actix"),
    ("rocket", "rocket"),
    ("warp", "warp"),
    ("poem", "poem"),
]

# Gemfile gem name → framework identifier
_RUBY_FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    ("rails", "rails"),
    ("grape", "grape"),
    ("sinatra", "sinatra"),
    ("hanami", "hanami"),
    ("roda", "roda"),
]

# pom.xml / build.gradle artifactId / text fragments → (framework, confidence)
_JVM_FRAMEWORK_INDICATORS: list[tuple[str, str, float]] = [
    ("spring-boot-starter-parent", "spring-boot", 0.95),
    ("spring-boot-starter-webflux", "spring-webflux", 0.95),
    ("spring-boot-starter-web", "spring-boot", 0.9),
    ("spring-boot-starter", "spring-boot", 0.85),
    ("org.springframework.boot", "spring-boot", 0.9),
    ("quarkus-bom", "quarkus", 0.95),
    ("io.quarkus", "quarkus", 0.9),
    ("micronaut-parent", "micronaut", 0.95),
    ("io.micronaut", "micronaut", 0.9),
]

_GEM_RE = re.compile(r"""^\s*gem\s+['"]([^'"]+)['"]""")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def detect_repo_framework(
    installation_token: str,
    installation_id: int,
    repo_full_name: str,
    root_dir: str | None,
) -> DetectFrameworkResponse:
    """Fetch manifest files and return a DetectFrameworkResponse.

    Results are cached per (installation_id, repo_full_name, root_dir)
    for _TTL_SECONDS to avoid hammering the GitHub API.
    """
    key = f"{installation_id}:{repo_full_name}:{root_dir or ''}"
    cached = _CACHE.get(key)
    if cached and time.monotonic() < cached[1]:
        return cached[0]

    files = await _probe_files(installation_token, repo_full_name, root_dir)
    result = _detect_from_files(files)
    _CACHE[key] = (result, time.monotonic() + _TTL_SECONDS)
    return result


# ---------------------------------------------------------------------------
# File fetching
# ---------------------------------------------------------------------------

async def _probe_files(
    token: str,
    repo_full_name: str,
    root_dir: str | None,
) -> dict[str, bytes]:
    """Fetch manifest files from the GitHub Contents API concurrently.

    Returns a dict mapping filename (basename, no path prefix) → raw bytes.
    Files that return 404 or error are silently skipped.
    """
    owner, repo = repo_full_name.split("/", 1)
    prefix = f"{root_dir.strip('/')}/" if root_dir else ""

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [
            _fetch_one(client, owner, repo, prefix + filename, filename, headers)
            for filename in _MANIFEST_FILES
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    files: dict[str, bytes] = {}
    for item in results:
        if isinstance(item, tuple):
            name, content = item
            files[name] = content
    return files


async def _fetch_one(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    path: str,
    filename: str,
    headers: dict[str, str],
) -> tuple[str, bytes] | None:
    """Fetch a single file from GitHub Contents API.

    Returns (filename, raw_bytes) or None when the file is absent.
    """
    import base64
    try:
        response = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}",
            headers=headers,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        raw = base64.b64decode(data["content"].replace("\n", ""))
        return (filename, raw)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Detection logic (pure functions — no network, easily unit-tested)
# ---------------------------------------------------------------------------

def _detect_from_files(files: dict[str, bytes]) -> DetectFrameworkResponse:
    """Determine language + framework from the fetched manifest files.

    Priority: Rust > Go > Python > Ruby > JVM > JavaScript.
    First match wins in each language's indicator list.
    """
    if "Cargo.toml" in files:
        return _detect_rust(files["Cargo.toml"])
    if "go.mod" in files:
        return _detect_go(files["go.mod"])
    if "pyproject.toml" in files or "requirements.txt" in files:
        return _detect_python(files)
    if "Gemfile" in files:
        return _detect_ruby(files["Gemfile"])
    if "pom.xml" in files:
        return _detect_jvm_maven(files["pom.xml"])
    if "build.gradle" in files:
        return _detect_jvm_gradle(files["build.gradle"], "build.gradle")
    if "build.gradle.kts" in files:
        return _detect_jvm_gradle(files["build.gradle.kts"], "build.gradle.kts")
    if "package.json" in files:
        return _detect_js(files)
    return DetectFrameworkResponse(confidence=0.0)


def _detect_rust(cargo_bytes: bytes) -> DetectFrameworkResponse:
    try:
        data = tomllib.loads(cargo_bytes.decode("utf-8", errors="replace"))
    except Exception:
        return DetectFrameworkResponse(language="rust", package_manager="cargo", confidence=0.6)

    deps: set[str] = set()
    for name in data.get("dependencies", {}):
        deps.add(name.lower())
    for name in data.get("workspace", {}).get("dependencies", {}):
        deps.add(name.lower())

    for pkg_name, framework in _RUST_FRAMEWORK_INDICATORS:
        if pkg_name in deps:
            return DetectFrameworkResponse(
                framework=framework,
                language="rust",
                package_manager="cargo",
                confidence=0.9,
            )
    return DetectFrameworkResponse(framework="rust", language="rust", package_manager="cargo", confidence=0.7)


def _detect_go(gomod_bytes: bytes) -> DetectFrameworkResponse:
    text = gomod_bytes.decode("utf-8", errors="replace")
    requires: list[str] = []
    in_block = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "require (":
            in_block = True
        elif stripped == ")" and in_block:
            in_block = False
        elif in_block:
            parts = stripped.split()
            if parts:
                requires.append(parts[0])
        elif stripped.startswith("require ") and not stripped.endswith("("):
            parts = stripped[8:].strip().split()
            if parts:
                requires.append(parts[0])

    for path_fragment, framework in _GO_FRAMEWORK_INDICATORS:
        for req in requires:
            if path_fragment in req:
                return DetectFrameworkResponse(
                    framework=framework,
                    language="go",
                    package_manager="go",
                    confidence=0.9,
                )
    return DetectFrameworkResponse(framework="go", language="go", package_manager="go", confidence=0.7)


def _detect_python(files: dict[str, bytes]) -> DetectFrameworkResponse:
    deps: set[str] = set()

    # pyproject.toml
    if "pyproject.toml" in files:
        try:
            data = tomllib.loads(files["pyproject.toml"].decode("utf-8", errors="replace"))
            # PEP 517 [project.dependencies]
            for dep_str in data.get("project", {}).get("dependencies", []):
                name = _extract_pkg_name(dep_str)
                if name:
                    deps.add(name)
            # Poetry [tool.poetry.dependencies]
            for name in data.get("tool", {}).get("poetry", {}).get("dependencies", {}):
                deps.add(name.lower())
        except Exception:
            pass

    # requirements.txt
    if "requirements.txt" in files:
        for line in files["requirements.txt"].decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            name = re.split(r"[><=!;@\[\s]", line.split("#")[0].strip())[0].strip().lower()
            if name:
                deps.add(name)

    framework: Optional[str] = None
    for pkg_name, fw in _PYTHON_FRAMEWORK_INDICATORS:
        if pkg_name in deps:
            framework = fw
            break

    pm = _detect_python_pm(files)

    return DetectFrameworkResponse(
        framework=framework,
        language="python",
        package_manager=pm,
        confidence=0.85 if framework else 0.5,
    )


def _detect_python_pm(files: dict[str, bytes]) -> str:
    if "uv.lock" in files:
        return "uv"
    if "poetry.lock" in files:
        return "poetry"
    if "Pipfile.lock" in files:
        return "pipenv"
    if "pyproject.toml" in files:
        try:
            data = tomllib.loads(files["pyproject.toml"].decode("utf-8", errors="replace"))
            tool = data.get("tool", {})
            if "poetry" in tool:
                return "poetry"
            if "uv" in tool:
                return "uv"
        except Exception:
            pass
    return "pip"


def _detect_ruby(gemfile_bytes: bytes) -> DetectFrameworkResponse:
    gems: set[str] = set()
    for line in gemfile_bytes.decode("utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _GEM_RE.match(stripped)
        if match:
            gems.add(match.group(1).lower())

    for gem_name, framework in _RUBY_FRAMEWORK_INDICATORS:
        if gem_name in gems:
            return DetectFrameworkResponse(
                framework=framework,
                language="ruby",
                package_manager="bundler",
                confidence=0.9,
            )
    return DetectFrameworkResponse(
        framework="ruby",
        language="ruby",
        package_manager="bundler",
        confidence=0.6,
    )


def _detect_jvm_maven(pom_bytes: bytes) -> DetectFrameworkResponse:
    try:
        root = ET.fromstring(pom_bytes.decode("utf-8", errors="replace"))
    except Exception:
        return DetectFrameworkResponse(language="java", package_manager="maven", confidence=0.5)

    # Collect all artifactId text values (with and without namespace)
    artifact_ids: list[str] = []
    for elem in root.iter():
        if elem.tag.endswith("artifactId") and elem.text:
            artifact_ids.append(elem.text.strip())

    for fragment, framework, confidence in _JVM_FRAMEWORK_INDICATORS:
        for aid in artifact_ids:
            if fragment in aid:
                return DetectFrameworkResponse(
                    framework=framework,
                    language="java",
                    package_manager="maven",
                    confidence=confidence,
                )
    return DetectFrameworkResponse(framework="java", language="java", package_manager="maven", confidence=0.6)


def _detect_jvm_gradle(gradle_bytes: bytes, filename: str) -> DetectFrameworkResponse:
    content = gradle_bytes.decode("utf-8", errors="replace")
    for fragment, framework, confidence in _JVM_FRAMEWORK_INDICATORS:
        if fragment in content:
            return DetectFrameworkResponse(
                framework=framework,
                language="java",
                package_manager="gradle",
                confidence=confidence,
            )
    return DetectFrameworkResponse(framework="java", language="java", package_manager="gradle", confidence=0.6)


def _detect_js(files: dict[str, bytes]) -> DetectFrameworkResponse:
    try:
        data = json.loads(files["package.json"].decode("utf-8", errors="replace"))
    except Exception:
        return DetectFrameworkResponse(language="javascript", confidence=0.4)

    all_deps: set[str] = set()
    all_deps.update(data.get("dependencies", {}).keys())
    all_deps.update(data.get("devDependencies", {}).keys())

    framework: Optional[str] = None
    for dep_name, fw in _JS_FRAMEWORK_INDICATORS:
        if dep_name in all_deps:
            framework = fw
            break

    pm = _detect_js_pm(files)

    return DetectFrameworkResponse(
        framework=framework,
        language="javascript",
        package_manager=pm,
        confidence=0.85 if framework else 0.5,
    )


def _detect_js_pm(files: dict[str, bytes]) -> str:
    for lock_file, pm in _JS_PM_LOCK_FILES:
        if lock_file in files:
            return pm
    return "npm"


def _extract_pkg_name(dep_str: str) -> str:
    name = re.split(r"[><=!;@\[\s]", dep_str.strip())[0].strip().lower()
    return name
