"""Tests for the C/C++ ecosystem detector."""

import json
from pathlib import Path

from runner.detector.cpp import detect_cpp
from runner.detector.orchestrator import detect


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestCppDetection:
    def test_detects_cmake_project(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "CMakeLists.txt",
            """
cmake_minimum_required(VERSION 3.20)
project(sample_cpp LANGUAGES CXX)
add_executable(app src/main.cpp)
""".strip(),
        )
        _write(tmp_path / "src" / "main.cpp", "int main() { return 0; }")

        result = detect_cpp(tmp_path)

        assert result.language == "cpp"
        assert result.package_manager == "cmake"
        assert result.install_cmd == "cmake -S . -B build"
        assert result.build_cmd == "cmake --build build"
        assert result.test_cmd == "ctest --test-dir build --output-on-failure"

    def test_detects_make_project_when_native_sources_exist(self, tmp_path: Path) -> None:
        _write(tmp_path / "Makefile", "all:\n\tg++ src/main.cpp -o app\n")
        _write(tmp_path / "src" / "main.cpp", "int main() { return 0; }")

        result = detect(tmp_path)

        assert result.language == "cpp"
        assert result.package_manager == "make"
        assert result.build_cmd == "make"
        assert result.test_cmd == "make test"

    def test_makefile_without_native_markers_does_not_force_cpp(self, tmp_path: Path) -> None:
        _write(tmp_path / "Makefile", "lint:\n\techo ok\n")
        _write(
            tmp_path / "package.json",
            json.dumps({"scripts": {"test": "vitest run"}}),
        )
        _write(tmp_path / "package-lock.json", "{}")

        result = detect(tmp_path)

        assert result.language == "javascript"
        assert result.package_manager == "npm"

    def test_cmake_takes_priority_over_package_json(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "CMakeLists.txt",
            """
cmake_minimum_required(VERSION 3.20)
project(native_app LANGUAGES C CXX)
add_executable(app src/main.cpp)
""".strip(),
        )
        _write(tmp_path / "src" / "main.cpp", "int main() { return 0; }")
        _write(
            tmp_path / "package.json",
            json.dumps({"scripts": {"test": "vitest run"}}),
        )
        _write(tmp_path / "package-lock.json", "{}")

        result = detect(tmp_path)

        assert result.language == "cpp"
        assert result.package_manager == "cmake"
