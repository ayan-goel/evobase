"""pyproject.toml parser for Python framework and command detection.

Uses stdlib tomllib (Python 3.11+). Handles both modern PEP 517
[project] tables and Poetry's [tool.poetry] layout.
"""

import logging
import tomllib
from pathlib import Path

from runner.detector.types import CommandSignal

logger = logging.getLogger(__name__)

# Ordered by specificity — first match wins.
FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    ("fastapi", "fastapi"),
    ("django", "django"),
    ("flask", "flask"),
    ("starlette", "starlette"),
    ("aiohttp", "aiohttp"),
    ("tornado", "tornado"),
    ("litestar", "litestar"),
]


def parse_pyproject(repo_dir: Path) -> dict[str, list[CommandSignal]]:
    """Parse pyproject.toml and return categorised command signals."""
    path = repo_dir / "pyproject.toml"
    if not path.exists():
        return {}

    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception as exc:
        logger.error("Failed to parse pyproject.toml: %s", exc)
        return {}

    signals: dict[str, list[CommandSignal]] = {}

    # Extract scripts from [tool.poetry.scripts] or [project.scripts]
    poetry_scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
    project_scripts = data.get("project", {}).get("scripts", {})
    all_scripts = {**project_scripts, **poetry_scripts}

    # Map script names to categories
    _add_script_signals(signals, all_scripts, source="pyproject.toml scripts")

    return signals


def detect_framework(repo_dir: Path) -> CommandSignal | None:
    """Detect Python framework from pyproject.toml dependencies."""
    path = repo_dir / "pyproject.toml"
    if not path.exists():
        return None

    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return None

    deps = _collect_deps(data)

    for pkg_name, framework in FRAMEWORK_INDICATORS:
        if pkg_name in deps:
            return CommandSignal(
                command=framework,
                source=f"pyproject.toml dependency: {pkg_name}",
                confidence=0.9,
            )
    return None


def detect_package_manager(repo_dir: Path) -> CommandSignal | None:
    """Detect Python package manager from pyproject.toml and lock files."""
    # Lock file has highest confidence
    if (repo_dir / "uv.lock").exists():
        return CommandSignal(command="uv", source="lock file: uv.lock", confidence=0.95)
    if (repo_dir / "poetry.lock").exists():
        return CommandSignal(command="poetry", source="lock file: poetry.lock", confidence=0.95)
    if (repo_dir / "Pipfile.lock").exists():
        return CommandSignal(command="pipenv", source="lock file: Pipfile.lock", confidence=0.95)

    path = repo_dir / "pyproject.toml"
    if not path.exists():
        return None

    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return None

    tool = data.get("tool", {})
    if "poetry" in tool:
        return CommandSignal(command="poetry", source="pyproject.toml [tool.poetry]", confidence=0.85)
    if "uv" in tool:
        return CommandSignal(command="uv", source="pyproject.toml [tool.uv]", confidence=0.85)

    # PEP 517 build-backend hints
    build_backend = data.get("build-system", {}).get("build-backend", "")
    if "poetry" in build_backend:
        return CommandSignal(command="poetry", source="pyproject.toml build-backend", confidence=0.80)

    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_deps(data: dict) -> set[str]:
    """Collect all dependency names from known pyproject.toml layouts."""
    deps: set[str] = set()

    # PEP 517 [project.dependencies] — list of "pkg>=version" strings
    for dep_str in data.get("project", {}).get("dependencies", []):
        name = _extract_pkg_name(dep_str)
        if name:
            deps.add(name)

    # Poetry [tool.poetry.dependencies] — dict of {name: version}
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    deps.update(k.lower() for k in poetry_deps)

    # Poetry dev-deps (older layout)
    poetry_dev = data.get("tool", {}).get("poetry", {}).get("dev-dependencies", {})
    deps.update(k.lower() for k in poetry_dev)

    # Poetry group deps (newer layout)
    for group in data.get("tool", {}).get("poetry", {}).get("group", {}).values():
        deps.update(k.lower() for k in group.get("dependencies", {}))

    # PEP 517 optional deps
    for extra_deps in data.get("project", {}).get("optional-dependencies", {}).values():
        for dep_str in extra_deps:
            name = _extract_pkg_name(dep_str)
            if name:
                deps.add(name)

    return deps


def _extract_pkg_name(dep_str: str) -> str:
    """Extract the bare package name from a PEP 508 dependency string."""
    import re
    # Strip everything from the first >, <, =, !, ;, @, [ onwards
    name = re.split(r"[><=!;@\[\s]", dep_str.strip())[0].strip().lower()
    return name


_SCRIPT_CATEGORY_MAP: dict[str, str] = {
    "test": "test",
    "tests": "test",
    "pytest": "test",
    "build": "build",
    "compile": "build",
    "typecheck": "typecheck",
    "mypy": "typecheck",
    "type-check": "typecheck",
}


def _add_script_signals(
    signals: dict[str, list[CommandSignal]],
    scripts: dict[str, str],
    source: str,
) -> None:
    for name, cmd in scripts.items():
        category = _SCRIPT_CATEGORY_MAP.get(name.lower())
        if category:
            signals.setdefault(category, []).append(
                CommandSignal(command=cmd, source=f"{source}.{name}", confidence=0.8)
            )
