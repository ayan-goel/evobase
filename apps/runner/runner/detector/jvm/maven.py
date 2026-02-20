"""pom.xml parser for JVM framework and build tool detection.

Uses xml.etree.ElementTree (stdlib) to parse Maven POM files.
Handles both direct dependency and parent POM patterns used by Spring Boot.
"""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from runner.detector.types import CommandSignal

logger = logging.getLogger(__name__)

# Maven XML namespace used by pom.xml files
_POM_NS = "http://maven.apache.org/POM/4.0.0"

# Maps artifactIds (substrings) to framework identifiers.
# Checked against <parent>, <dependency>, and <plugin> artifactIds.
FRAMEWORK_INDICATORS: list[tuple[str, str, float]] = [
    ("spring-boot-starter-parent", "spring-boot", 0.95),
    ("spring-boot-starter-webflux", "spring-webflux", 0.95),
    ("spring-boot-starter-web", "spring-boot", 0.9),
    ("spring-boot-starter", "spring-boot", 0.85),
    ("quarkus-bom", "quarkus", 0.95),
    ("quarkus-universe-bom", "quarkus", 0.9),
    ("micronaut-parent", "micronaut", 0.95),
    ("micronaut-bom", "micronaut", 0.9),
]


def _ns(tag: str) -> str:
    return f"{{{_POM_NS}}}{tag}"


def _parse_artifact_ids(root: ET.Element) -> list[str]:
    """Collect all artifactId values from parent, dependencies, and plugins."""
    artifact_ids: list[str] = []

    # <parent> artifactId
    parent = root.find(_ns("parent"))
    if parent is not None:
        aid = parent.findtext(_ns("artifactId"))
        if aid:
            artifact_ids.append(aid.strip())

    # <dependencies>/<dependency> artifactIds
    for dep in root.findall(f".//{_ns('dependency')}"):
        aid = dep.findtext(_ns("artifactId"))
        if aid:
            artifact_ids.append(aid.strip())

    # <plugins>/<plugin> artifactIds
    for plugin in root.findall(f".//{_ns('plugin')}"):
        aid = plugin.findtext(_ns("artifactId"))
        if aid:
            artifact_ids.append(aid.strip())

    # Handle pom.xml files without namespace (some minimal POMs omit it)
    for dep in root.findall(".//dependency"):
        aid = dep.findtext("artifactId")
        if aid:
            artifact_ids.append(aid.strip())
    for plugin in root.findall(".//plugin"):
        aid = plugin.findtext("artifactId")
        if aid:
            artifact_ids.append(aid.strip())

    return artifact_ids


def detect_framework(repo_dir: Path) -> CommandSignal | None:
    """Detect JVM framework from pom.xml."""
    path = repo_dir / "pom.xml"
    if not path.exists():
        return None

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as exc:
        logger.error("Failed to parse pom.xml: %s", exc)
        return CommandSignal(
            command="java",
            source="pom.xml (parse error)",
            confidence=0.5,
        )

    artifact_ids = _parse_artifact_ids(root)

    for fragment, framework, confidence in FRAMEWORK_INDICATORS:
        for aid in artifact_ids:
            if fragment in aid:
                return CommandSignal(
                    command=framework,
                    source=f"pom.xml artifactId: {aid}",
                    confidence=confidence,
                )

    return CommandSignal(
        command="java",
        source="pom.xml (no known framework detected)",
        confidence=0.6,
    )


def detect_build_tool(repo_dir: Path) -> str:
    """Return 'maven' with wrapper detection."""
    if (repo_dir / "mvnw").exists():
        return "maven-wrapper"
    return "maven"


def get_install_cmd(repo_dir: Path) -> str:
    if (repo_dir / "mvnw").exists():
        return "./mvnw install -DskipTests"
    return "mvn install -DskipTests"


def get_test_cmd(repo_dir: Path) -> str:
    if (repo_dir / "mvnw").exists():
        return "./mvnw test"
    return "mvn test"


def get_build_cmd(repo_dir: Path) -> str:
    if (repo_dir / "mvnw").exists():
        return "./mvnw package -DskipTests"
    return "mvn package -DskipTests"
