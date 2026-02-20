"""JVM ecosystem detector (Maven / Gradle).

Entry point: detect_jvm(repo_dir) -> DetectionResult

Probes pom.xml first (Maven), then build.gradle / build.gradle.kts (Gradle).
Supports Spring Boot, Quarkus, Micronaut, and generic Java/Kotlin projects.
"""

from pathlib import Path

from runner.detector.jvm import gradle, maven
from runner.detector.types import CommandSignal, DetectionResult


def detect_jvm(repo_dir: Path) -> DetectionResult:
    """Run full JVM detection on a repository directory."""
    result = DetectionResult(language="java")
    all_confidences: list[float] = []

    use_maven = (repo_dir / "pom.xml").exists()

    if use_maven:
        # Maven project
        result.package_manager = "maven"
        result.install_cmd = maven.get_install_cmd(repo_dir)
        result.build_cmd = maven.get_build_cmd(repo_dir)
        result.test_cmd = maven.get_test_cmd(repo_dir)
        result.evidence.append(
            f"package_manager: maven (pom.xml found, "
            f"wrapper={'yes' if (repo_dir / 'mvnw').exists() else 'no'})"
        )

        fw_signal = maven.detect_framework(repo_dir)
    else:
        # Gradle project
        result.package_manager = "gradle"
        result.install_cmd = gradle.get_install_cmd(repo_dir)
        result.build_cmd = gradle.get_build_cmd(repo_dir)
        result.test_cmd = gradle.get_test_cmd(repo_dir)
        result.evidence.append(
            f"package_manager: gradle (build.gradle found, "
            f"wrapper={'yes' if (repo_dir / 'gradlew').exists() else 'no'})"
        )

        fw_signal = gradle.detect_framework(repo_dir)

    if fw_signal:
        result.framework = fw_signal.command
        result.evidence.append(f"framework: {fw_signal.command} ({fw_signal.source})")
        all_confidences.append(fw_signal.confidence)

    result.confidence = min(all_confidences) if all_confidences else 0.5
    return result


def _pick_best(signals: list[CommandSignal]) -> CommandSignal | None:
    if not signals:
        return None
    return max(signals, key=lambda s: s.confidence)
