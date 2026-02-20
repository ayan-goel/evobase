"""go.mod parser for Go framework and command detection.

Parses go.mod with a simple line-by-line parser — no external library needed.
Handles both single-line and multi-line require blocks.
"""

import logging
from pathlib import Path

from runner.detector.types import CommandSignal

logger = logging.getLogger(__name__)

# Maps go.mod module paths (substrings) to framework identifiers.
# Ordered by specificity — first match wins.
FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    ("gin-gonic/gin", "gin"),
    ("labstack/echo", "echo"),
    ("gofiber/fiber", "fiber"),
    ("go-chi/chi", "chi"),
    ("gorilla/mux", "gorilla"),
    ("go-kit/kit", "go"),
    ("beego/beego", "go"),
]

# Default commands for Go projects
DEFAULT_INSTALL_CMD = "go mod download"
DEFAULT_BUILD_CMD = "go build ./..."
DEFAULT_TEST_CMD = "go test ./..."
DEFAULT_TYPECHECK_CMD = "go vet ./..."


def parse_gomod(repo_dir: Path) -> dict:
    """Parse go.mod and return a dict with module, go_version, and requires list."""
    path = repo_dir / "go.mod"
    if not path.exists():
        return {}

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to read go.mod: %s", exc)
        return {}

    module = ""
    go_version = ""
    requires: list[str] = []
    in_require_block = False

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("module "):
            module = stripped[7:].strip()
        elif stripped.startswith("go ") and not in_require_block:
            go_version = stripped[3:].strip()
        elif stripped == "require (":
            in_require_block = True
        elif stripped == ")":
            in_require_block = False
        elif in_require_block:
            # Inside require block: "github.com/foo/bar v1.0.0 // indirect"
            parts = stripped.split()
            if parts:
                requires.append(parts[0])
        elif stripped.startswith("require ") and not stripped.endswith("("):
            # Single-line require: "require github.com/foo/bar v1.0.0"
            parts = stripped[8:].strip().split()
            if parts:
                requires.append(parts[0])

    return {"module": module, "go_version": go_version, "requires": requires}


def detect_framework(repo_dir: Path) -> CommandSignal | None:
    """Detect Go web framework from go.mod dependencies."""
    parsed = parse_gomod(repo_dir)
    if not parsed:
        return None

    requires = parsed.get("requires", [])

    for path_fragment, framework in FRAMEWORK_INDICATORS:
        for req in requires:
            if path_fragment in req:
                return CommandSignal(
                    command=framework,
                    source=f"go.mod require: {req}",
                    confidence=0.9,
                )

    # go.mod exists but no known framework
    return CommandSignal(
        command="go",
        source="go.mod (no known framework detected)",
        confidence=0.7,
    )
