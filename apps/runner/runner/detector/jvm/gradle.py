"""build.gradle / build.gradle.kts parser for JVM framework detection.

Uses a line-by-line text scan — no Groovy/Kotlin AST parser needed.
Handles both Groovy DSL (build.gradle) and Kotlin DSL (build.gradle.kts).
"""

import logging
from pathlib import Path

from runner.detector.types import CommandSignal

logger = logging.getLogger(__name__)

# Maps text fragments found in build.gradle to framework identifiers.
# Checked against the raw file content (case-sensitive, as Gradle files are).
FRAMEWORK_INDICATORS: list[tuple[str, str, float]] = [
    ("org.springframework.boot", "spring-boot", 0.95),
    ("io.spring.dependency-management", "spring-boot", 0.85),
    ("io.quarkus", "quarkus", 0.95),
    ("io.micronaut", "micronaut", 0.9),
    ("io.micronaut.application", "micronaut", 0.95),
]


def _read_gradle_file(repo_dir: Path) -> tuple[str, str]:
    """Return (content, filename) for the first gradle build file found."""
    for name in ("build.gradle.kts", "build.gradle"):
        path = repo_dir / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8"), name
            except Exception as exc:
                logger.error("Failed to read %s: %s", name, exc)
    return "", ""


def detect_framework(repo_dir: Path) -> CommandSignal | None:
    """Detect JVM framework from build.gradle / build.gradle.kts."""
    content, filename = _read_gradle_file(repo_dir)
    if not content:
        return None

    for fragment, framework, confidence in FRAMEWORK_INDICATORS:
        if fragment in content:
            return CommandSignal(
                command=framework,
                source=f"{filename}: {fragment}",
                confidence=confidence,
            )

    return CommandSignal(
        command="java",
        source=f"{filename} (no known framework detected)",
        confidence=0.6,
    )


def detect_build_tool(repo_dir: Path) -> str:
    """Return 'gradle' or 'gradle-wrapper' if gradlew script exists."""
    if (repo_dir / "gradlew").exists():
        return "gradle-wrapper"
    return "gradle"


def get_install_cmd(repo_dir: Path) -> str:
    prefix = "./gradlew" if (repo_dir / "gradlew").exists() else "gradle"
    return f"{prefix} build -x test"


def get_test_cmd(repo_dir: Path) -> str:
    prefix = "./gradlew" if (repo_dir / "gradlew").exists() else "gradle"
    return f"{prefix} test"


def get_build_cmd(repo_dir: Path) -> str:
    prefix = "./gradlew" if (repo_dir / "gradlew").exists() else "gradle"
    return f"{prefix} assemble"
