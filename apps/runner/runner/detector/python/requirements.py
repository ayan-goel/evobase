"""requirements.txt parser for Python framework detection.

Parses requirements.txt (and requirements/*.txt) line-by-line.
Strips version specifiers, extras, comments, and pip flags.
"""

import logging
import re
from pathlib import Path

from runner.detector.types import CommandSignal

logger = logging.getLogger(__name__)

FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    ("fastapi", "fastapi"),
    ("django", "django"),
    ("flask", "flask"),
    ("starlette", "starlette"),
    ("aiohttp", "aiohttp"),
    ("tornado", "tornado"),
    ("litestar", "litestar"),
]


def detect_framework(repo_dir: Path) -> CommandSignal | None:
    """Detect Python framework from requirements files."""
    packages = _collect_packages(repo_dir)

    for pkg_name, framework in FRAMEWORK_INDICATORS:
        if pkg_name in packages:
            return CommandSignal(
                command=framework,
                source="requirements.txt",
                confidence=0.85,
            )
    return None


def detect_package_manager(repo_dir: Path) -> CommandSignal | None:
    """Signal that pip is the package manager when requirements.txt exists."""
    req_path = repo_dir / "requirements.txt"
    if req_path.exists():
        return CommandSignal(
            command="pip",
            source="requirements.txt",
            confidence=0.7,
        )
    return None


def _collect_packages(repo_dir: Path) -> set[str]:
    """Collect normalised package names from all requirements files."""
    packages: set[str] = set()

    # requirements.txt at root
    _parse_file(repo_dir / "requirements.txt", packages)

    # requirements/*.txt (e.g. requirements/base.txt)
    req_dir = repo_dir / "requirements"
    if req_dir.is_dir():
        for req_file in req_dir.glob("*.txt"):
            _parse_file(req_file, packages)

    return packages


def _parse_file(path: Path, packages: set[str]) -> None:
    if not path.exists():
        return

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return

    for line in text.splitlines():
        line = line.strip()
        # Skip comments, blank lines, and pip flags (-r, -c, --index-url, etc.)
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip inline comments
        line = line.split("#")[0].strip()
        if not line:
            continue
        # Extract bare package name (before >, <, =, !, ;, @, [)
        name = re.split(r"[><=!;@\[\s]", line)[0].strip().lower()
        # Normalise dashes/underscores for matching
        name = name.replace("-", "_").replace(".", "_")
        if name:
            packages.add(name)
            # Also add the original form (pre-normalisation) for safety
            raw = re.split(r"[><=!;@\[\s]", line)[0].strip().lower()
            packages.add(raw)
