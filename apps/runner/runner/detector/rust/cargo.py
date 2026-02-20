"""Cargo.toml parser for Rust framework and command detection.

Uses stdlib tomllib (Python 3.11+) to parse Cargo.toml.
Handles standard single-crate and workspace layouts.
"""

import logging
import tomllib
from pathlib import Path

from runner.detector.types import CommandSignal

logger = logging.getLogger(__name__)

# Maps Cargo.toml dependency names to framework identifiers.
# Ordered by specificity — first match wins.
FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    ("axum", "axum"),
    ("actix-web", "actix"),
    ("rocket", "rocket"),
    ("warp", "warp"),
    ("poem", "poem"),
    ("salvo", "salvo"),
    ("tide", "tide"),
]

# Default commands for Rust / Cargo projects
DEFAULT_INSTALL_CMD = "cargo fetch"
DEFAULT_BUILD_CMD = "cargo build"
DEFAULT_TEST_CMD = "cargo test"
DEFAULT_TYPECHECK_CMD = "cargo check"


def parse_cargo(repo_dir: Path) -> dict:
    """Parse Cargo.toml and return the raw dict."""
    path = repo_dir / "Cargo.toml"
    if not path.exists():
        return {}

    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception as exc:
        logger.error("Failed to parse Cargo.toml: %s", exc)
        return {}


def detect_framework(repo_dir: Path) -> CommandSignal | None:
    """Detect Rust web framework from Cargo.toml [dependencies]."""
    data = parse_cargo(repo_dir)
    if not data:
        return None

    # Collect all dependency names from standard and workspace layouts
    deps: set[str] = set()

    # Standard crate [dependencies]
    for name in data.get("dependencies", {}):
        deps.add(name.lower())

    # Workspace members may declare deps at the workspace level
    for name in data.get("workspace", {}).get("dependencies", {}):
        deps.add(name.lower())

    for pkg_name, framework in FRAMEWORK_INDICATORS:
        if pkg_name in deps:
            return CommandSignal(
                command=framework,
                source=f"Cargo.toml dependency: {pkg_name}",
                confidence=0.9,
            )

    # Cargo.toml exists but no known web framework
    return CommandSignal(
        command="rust",
        source="Cargo.toml (no known web framework detected)",
        confidence=0.7,
    )
