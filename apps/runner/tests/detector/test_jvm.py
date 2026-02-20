"""Tests for the JVM ecosystem detector (Maven + Gradle).

All tests use in-memory fixtures written to tmp_path — no real repos cloned.
"""

from pathlib import Path

import pytest

from runner.detector.jvm import detect_jvm
from runner.detector.jvm.maven import detect_framework as maven_detect_framework
from runner.detector.jvm.gradle import detect_framework as gradle_detect_framework
from runner.detector.orchestrator import detect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pom(tmp_path: Path, content: str) -> Path:
    (tmp_path / "pom.xml").write_text(content, encoding="utf-8")
    return tmp_path


def _gradle(tmp_path: Path, content: str, kotlin: bool = False) -> Path:
    filename = "build.gradle.kts" if kotlin else "build.gradle"
    (tmp_path / filename).write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# pom.xml fixtures
# ---------------------------------------------------------------------------

SPRING_BOOT_POM = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.0</version>
  </parent>
  <groupId>com.example</groupId>
  <artifactId>myapp</artifactId>
  <version>0.0.1-SNAPSHOT</version>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
  </dependencies>
</project>
"""

SPRING_WEBFLUX_POM = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>reactive-app</artifactId>
  <version>1.0.0</version>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-webflux</artifactId>
    </dependency>
  </dependencies>
</project>
"""

QUARKUS_POM = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>quarkus-app</artifactId>
  <version>1.0.0</version>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>io.quarkus.platform</groupId>
        <artifactId>quarkus-bom</artifactId>
        <version>3.5.0</version>
        <type>pom</type>
        <scope>import</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>
</project>
"""

MINIMAL_POM = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>plain-java</artifactId>
  <version>1.0.0</version>
</project>
"""


# ---------------------------------------------------------------------------
# build.gradle fixtures
# ---------------------------------------------------------------------------

SPRING_BOOT_GRADLE = """\
plugins {
    id 'org.springframework.boot' version '3.2.0'
    id 'io.spring.dependency-management' version '1.1.4'
    id 'java'
}

group = 'com.example'
version = '0.0.1-SNAPSHOT'

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
}
"""

SPRING_BOOT_KTS = """\
plugins {
    id("org.springframework.boot") version "3.2.0"
    id("io.spring.dependency-management") version "1.1.4"
    kotlin("jvm") version "1.9.21"
}

group = "com.example"
version = "0.0.1-SNAPSHOT"

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
}
"""

QUARKUS_GRADLE = """\
plugins {
    id 'java'
    id 'io.quarkus'
}

group = 'com.example'
version = '1.0.0'
"""

MINIMAL_GRADLE = """\
plugins {
    id 'java'
}

group = 'com.example'
version = '1.0.0'
"""


# ---------------------------------------------------------------------------
# Maven pom.xml detection tests
# ---------------------------------------------------------------------------

class TestMavenParsing:
    def test_spring_boot_detected_from_parent(self, tmp_path):
        _pom(tmp_path, SPRING_BOOT_POM)
        result = detect_jvm(tmp_path)
        assert result.framework == "spring-boot"
        assert result.language == "java"
        assert result.package_manager == "maven"

    def test_spring_webflux_detected_from_dependency(self, tmp_path):
        _pom(tmp_path, SPRING_WEBFLUX_POM)
        result = detect_jvm(tmp_path)
        assert result.framework == "spring-webflux"

    def test_quarkus_detected_from_bom(self, tmp_path):
        _pom(tmp_path, QUARKUS_POM)
        result = detect_jvm(tmp_path)
        assert result.framework == "quarkus"

    def test_minimal_pom_falls_back_to_java_generic(self, tmp_path):
        _pom(tmp_path, MINIMAL_POM)
        result = detect_jvm(tmp_path)
        assert result.framework == "java"
        assert result.language == "java"

    def test_spring_boot_confidence_is_high(self, tmp_path):
        _pom(tmp_path, SPRING_BOOT_POM)
        signal = maven_detect_framework(tmp_path)
        assert signal is not None
        assert signal.confidence >= 0.9

    def test_invalid_pom_returns_partial_result(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<notxml>", encoding="utf-8")
        result = detect_jvm(tmp_path)
        assert result.language == "java"
        assert result.package_manager == "maven"


# ---------------------------------------------------------------------------
# Gradle build file detection tests
# ---------------------------------------------------------------------------

class TestGradleParsing:
    def test_spring_boot_detected_from_gradle(self, tmp_path):
        _gradle(tmp_path, SPRING_BOOT_GRADLE)
        result = detect_jvm(tmp_path)
        assert result.framework == "spring-boot"
        assert result.language == "java"
        assert result.package_manager == "gradle"

    def test_spring_boot_detected_from_kotlin_dsl(self, tmp_path):
        _gradle(tmp_path, SPRING_BOOT_KTS, kotlin=True)
        result = detect_jvm(tmp_path)
        assert result.framework == "spring-boot"

    def test_quarkus_detected_from_gradle(self, tmp_path):
        _gradle(tmp_path, QUARKUS_GRADLE)
        result = detect_jvm(tmp_path)
        assert result.framework == "quarkus"

    def test_minimal_gradle_falls_back_to_java_generic(self, tmp_path):
        _gradle(tmp_path, MINIMAL_GRADLE)
        result = detect_jvm(tmp_path)
        assert result.framework == "java"


# ---------------------------------------------------------------------------
# Default commands and wrapper detection
# ---------------------------------------------------------------------------

class TestDefaultCommands:
    def test_maven_install_cmd(self, tmp_path):
        _pom(tmp_path, SPRING_BOOT_POM)
        result = detect_jvm(tmp_path)
        assert "mvn" in result.install_cmd
        assert "DskipTests" in result.install_cmd

    def test_maven_test_cmd(self, tmp_path):
        _pom(tmp_path, SPRING_BOOT_POM)
        result = detect_jvm(tmp_path)
        assert "mvn test" in result.test_cmd

    def test_maven_wrapper_used_when_mvnw_exists(self, tmp_path):
        _pom(tmp_path, SPRING_BOOT_POM)
        (tmp_path / "mvnw").write_text("#!/bin/sh", encoding="utf-8")
        result = detect_jvm(tmp_path)
        assert result.install_cmd.startswith("./mvnw")
        assert result.test_cmd.startswith("./mvnw")

    def test_gradle_install_cmd(self, tmp_path):
        _gradle(tmp_path, SPRING_BOOT_GRADLE)
        result = detect_jvm(tmp_path)
        assert "gradlew" in result.install_cmd or "gradle" in result.install_cmd

    def test_gradle_wrapper_used_when_gradlew_exists(self, tmp_path):
        _gradle(tmp_path, SPRING_BOOT_GRADLE)
        (tmp_path / "gradlew").write_text("#!/bin/sh", encoding="utf-8")
        result = detect_jvm(tmp_path)
        assert result.install_cmd.startswith("./gradlew")
        assert result.test_cmd.startswith("./gradlew")

    def test_maven_takes_priority_over_gradle_when_both_present(self, tmp_path):
        """pom.xml takes priority over build.gradle when both exist."""
        _pom(tmp_path, SPRING_BOOT_POM)
        _gradle(tmp_path, QUARKUS_GRADLE)
        result = detect_jvm(tmp_path)
        assert result.package_manager == "maven"


# ---------------------------------------------------------------------------
# Orchestrator routing
# ---------------------------------------------------------------------------

class TestOrchestratorRouting:
    def test_pom_xml_routes_to_jvm_detector(self, tmp_path):
        _pom(tmp_path, SPRING_BOOT_POM)
        result = detect(tmp_path)
        assert result.language == "java"
        assert result.framework == "spring-boot"

    def test_build_gradle_routes_to_jvm_detector(self, tmp_path):
        _gradle(tmp_path, SPRING_BOOT_GRADLE)
        result = detect(tmp_path)
        assert result.language == "java"

    def test_build_gradle_kts_routes_to_jvm_detector(self, tmp_path):
        _gradle(tmp_path, SPRING_BOOT_KTS, kotlin=True)
        result = detect(tmp_path)
        assert result.language == "java"

    def test_ruby_gemfile_takes_priority_over_jvm(self, tmp_path):
        """Gemfile probe runs before JVM probe in priority order."""
        (tmp_path / "Gemfile").write_text(
            "source 'https://rubygems.org'\ngem 'rails'\n", encoding="utf-8"
        )
        _pom(tmp_path, SPRING_BOOT_POM)
        result = detect(tmp_path)
        assert result.language == "ruby"

    def test_jvm_takes_priority_over_package_json(self, tmp_path):
        _pom(tmp_path, SPRING_BOOT_POM)
        (tmp_path / "package.json").write_text(
            '{"dependencies": {"next": "14.0.0"}}', encoding="utf-8"
        )
        result = detect(tmp_path)
        assert result.language == "java"
