"""C/C++ ecosystem detector.

Entry point: detect_cpp(repo_dir) -> DetectionResult
"""

from pathlib import Path

from runner.detector.types import DetectionResult

DEFAULT_CMAKE_INSTALL_CMD = "cmake -S . -B build"
DEFAULT_CMAKE_BUILD_CMD = "cmake --build build"
DEFAULT_CMAKE_TEST_CMD = "ctest --test-dir build --output-on-failure"

DEFAULT_MAKE_INSTALL_CMD = "true"
DEFAULT_MAKE_BUILD_CMD = "make"
DEFAULT_MAKE_TEST_CMD = "make test"


def detect_cpp(repo_dir: Path) -> DetectionResult:
    """Run C/C++ detection using CMake or Makefile markers."""
    result = DetectionResult(language="cpp")
    use_cmake = (repo_dir / "CMakeLists.txt").exists()

    if use_cmake:
        result.package_manager = "cmake"
        result.install_cmd = DEFAULT_CMAKE_INSTALL_CMD
        result.build_cmd = DEFAULT_CMAKE_BUILD_CMD
        result.test_cmd = DEFAULT_CMAKE_TEST_CMD
        result.framework = "cmake"
        result.confidence = 0.7
        result.evidence.append("package_manager: cmake (CMakeLists.txt present)")
        result.evidence.append(f"install_cmd: {DEFAULT_CMAKE_INSTALL_CMD} (cmake default)")
        result.evidence.append(f"build_cmd: {DEFAULT_CMAKE_BUILD_CMD} (cmake default)")
        result.evidence.append(f"test_cmd: {DEFAULT_CMAKE_TEST_CMD} (cmake default)")
        return result

    result.package_manager = "make"
    result.install_cmd = DEFAULT_MAKE_INSTALL_CMD
    result.build_cmd = DEFAULT_MAKE_BUILD_CMD
    result.test_cmd = DEFAULT_MAKE_TEST_CMD
    result.framework = "cpp"
    result.confidence = 0.6
    result.evidence.append("package_manager: make (Makefile + native source markers)")
    result.evidence.append(f"install_cmd: {DEFAULT_MAKE_INSTALL_CMD} (make default)")
    result.evidence.append(f"build_cmd: {DEFAULT_MAKE_BUILD_CMD} (make default)")
    result.evidence.append(f"test_cmd: {DEFAULT_MAKE_TEST_CMD} (make default)")
    return result
