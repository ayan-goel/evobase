"""Go ecosystem detector.

Entry point: detect_go(repo_dir) -> DetectionResult
"""

from pathlib import Path

from runner.detector.go.gomod import (
    DEFAULT_BUILD_CMD,
    DEFAULT_INSTALL_CMD,
    DEFAULT_TEST_CMD,
    DEFAULT_TYPECHECK_CMD,
    detect_framework,
)
from runner.detector.types import DetectionResult


def detect_go(repo_dir: Path) -> DetectionResult:
    """Run full Go detection on a repository directory."""
    result = DetectionResult(language="go")

    # Package manager is always the Go toolchain
    result.package_manager = "go"
    result.evidence.append("package_manager: go (go.mod present)")

    # Install / build / test / typecheck defaults
    result.install_cmd = DEFAULT_INSTALL_CMD
    result.build_cmd = DEFAULT_BUILD_CMD
    result.test_cmd = DEFAULT_TEST_CMD
    result.typecheck_cmd = DEFAULT_TYPECHECK_CMD
    result.evidence.append(f"install_cmd: {DEFAULT_INSTALL_CMD} (go default)")
    result.evidence.append(f"build_cmd: {DEFAULT_BUILD_CMD} (go default)")
    result.evidence.append(f"test_cmd: {DEFAULT_TEST_CMD} (go default)")
    result.evidence.append(f"typecheck_cmd: {DEFAULT_TYPECHECK_CMD} (go default)")

    # Framework detection
    fw_signal = detect_framework(repo_dir)
    if fw_signal:
        result.framework = fw_signal.command
        result.evidence.append(f"framework: {fw_signal.command} ({fw_signal.source})")
        result.confidence = fw_signal.confidence
    else:
        result.framework = "go"
        result.confidence = 0.7

    return result
