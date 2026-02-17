"""package.json parser for command and framework detection.

Extracts install/build/test/typecheck commands from the scripts block,
and infers the framework from dependencies.
"""

import json
import logging
from pathlib import Path

from runner.detector.types import CommandSignal

logger = logging.getLogger(__name__)

# Maps dependency names to framework identifiers.
# Order matters — first match wins. More specific deps go first.
FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
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

# Maps script names to command categories.
# The first matching script in each category is used.
SCRIPT_CATEGORIES: dict[str, list[str]] = {
    "build": ["build", "build:prod", "compile"],
    "test": ["test", "test:run", "test:unit", "spec"],
    "typecheck": ["typecheck", "type-check", "tsc", "types"],
    "lint": ["lint", "lint:fix"],
}


def parse_package_json(repo_dir: Path) -> dict[str, list[CommandSignal]]:
    """Parse package.json and extract command signals.

    Returns a dict mapping categories (build, test, typecheck, etc.)
    to lists of CommandSignal with confidence scores.
    """
    pkg_path = repo_dir / "package.json"
    if not pkg_path.exists():
        logger.warning("No package.json found at %s", pkg_path)
        return {}

    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("Failed to parse package.json: %s", exc)
        return {}

    signals: dict[str, list[CommandSignal]] = {}
    scripts = data.get("scripts", {})

    for category, script_names in SCRIPT_CATEGORIES.items():
        for name in script_names:
            if name in scripts:
                signals.setdefault(category, []).append(
                    CommandSignal(
                        command=f"{_placeholder_pm()} run {name}",
                        source=f"package.json scripts.{name}",
                        confidence=0.9,
                    )
                )

    return signals


def detect_framework(repo_dir: Path) -> CommandSignal | None:
    """Detect the framework from package.json dependencies.

    Checks both dependencies and devDependencies.
    Returns the first matching framework signal.
    """
    pkg_path = repo_dir / "package.json"
    if not pkg_path.exists():
        return None

    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    all_deps: set[str] = set()
    all_deps.update(data.get("dependencies", {}).keys())
    all_deps.update(data.get("devDependencies", {}).keys())

    for dep_name, framework in FRAMEWORK_INDICATORS:
        if dep_name in all_deps:
            return CommandSignal(
                command=framework,
                source=f"package.json dependency: {dep_name}",
                confidence=0.85,
            )

    return None


def detect_package_manager(repo_dir: Path) -> CommandSignal:
    """Detect the package manager from lock files.

    Priority order:
    1. pnpm-lock.yaml -> pnpm
    2. yarn.lock -> yarn
    3. bun.lockb -> bun
    4. package-lock.json -> npm (default)

    Lock files are the highest-confidence signal.
    """
    lock_files: list[tuple[str, str]] = [
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lockb", "bun"),
        ("package-lock.json", "npm"),
    ]

    for filename, pm in lock_files:
        if (repo_dir / filename).exists():
            return CommandSignal(
                command=pm,
                source=f"lock file: {filename}",
                confidence=0.95,
            )

    # Fallback: check if package.json has packageManager field
    pkg_path = repo_dir / "package.json"
    if pkg_path.exists():
        try:
            data = json.loads(pkg_path.read_text(encoding="utf-8"))
            pm_field = data.get("packageManager", "")
            if pm_field.startswith("pnpm"):
                return CommandSignal(command="pnpm", source="package.json packageManager field", confidence=0.9)
            if pm_field.startswith("yarn"):
                return CommandSignal(command="yarn", source="package.json packageManager field", confidence=0.9)
            if pm_field.startswith("bun"):
                return CommandSignal(command="bun", source="package.json packageManager field", confidence=0.9)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # Default to npm if package.json exists but no lock file found
    if pkg_path.exists():
        return CommandSignal(
            command="npm",
            source="default (no lock file found)",
            confidence=0.5,
        )

    return CommandSignal(
        command="npm",
        source="fallback (no package.json)",
        confidence=0.1,
    )


def get_install_command(package_manager: str) -> str:
    """Return the canonical install command for a package manager."""
    install_commands: dict[str, str] = {
        "npm": "npm ci",
        "yarn": "yarn install --frozen-lockfile",
        "pnpm": "pnpm install --frozen-lockfile",
        "bun": "bun install --frozen-lockfile",
    }
    return install_commands.get(package_manager, "npm ci")


def _placeholder_pm() -> str:
    """Placeholder used in script commands. Replaced by orchestrator."""
    return "{pm}"
