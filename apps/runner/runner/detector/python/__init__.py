"""Python ecosystem detector.

Entry point: detect_python(repo_dir) -> DetectionResult
"""

from pathlib import Path

from runner.detector.python.defaults import (
    DEFAULT_TEST_CMD,
    FALLBACK_INSTALL_CMD,
    FRAMEWORK_TEST_CMDS,
    INSTALL_CMDS,
)
from runner.detector.python import pyproject, requirements
from runner.detector.types import CommandSignal, DetectionResult


def detect_python(repo_dir: Path) -> DetectionResult:
    """Run full Python detection on a repository directory."""
    result = DetectionResult(language="python")
    all_confidences: list[float] = []

    # 1. Package manager — pyproject.toml signals take priority over requirements.txt
    pm_signal = pyproject.detect_package_manager(repo_dir)
    if pm_signal is None:
        pm_signal = requirements.detect_package_manager(repo_dir)

    if pm_signal:
        result.package_manager = pm_signal.command
        result.evidence.append(f"package_manager: {pm_signal.command} ({pm_signal.source})")
        all_confidences.append(pm_signal.confidence)

    # 2. Install command
    pm = result.package_manager or "pip"
    result.install_cmd = INSTALL_CMDS.get(pm, FALLBACK_INSTALL_CMD)
    result.evidence.append(f"install_cmd: {result.install_cmd} (derived from {pm})")

    # 3. Framework — pyproject.toml first, requirements.txt fallback
    fw_signal = pyproject.detect_framework(repo_dir)
    if fw_signal is None:
        fw_signal = requirements.detect_framework(repo_dir)

    if fw_signal:
        result.framework = fw_signal.command
        result.evidence.append(f"framework: {fw_signal.command} ({fw_signal.source})")
        all_confidences.append(fw_signal.confidence)

    # 4. Command signals from pyproject.toml scripts
    pkg_signals = pyproject.parse_pyproject(repo_dir)
    for category in ("build", "test", "typecheck"):
        best = _pick_best(pkg_signals.get(category, []))
        if best:
            setattr(result, f"{category}_cmd", best.command)
            result.evidence.append(f"{category}_cmd: {best.command} ({best.source})")
            all_confidences.append(best.confidence)

    # 5. Default test command if none detected
    if result.test_cmd is None:
        framework = result.framework
        result.test_cmd = FRAMEWORK_TEST_CMDS.get(framework or "", DEFAULT_TEST_CMD)
        result.evidence.append(f"test_cmd: {result.test_cmd} (default for {framework or 'python'})")

    result.confidence = min(all_confidences) if all_confidences else 0.5
    return result


def _pick_best(signals: list[CommandSignal]) -> CommandSignal | None:
    if not signals:
        return None
    return max(signals, key=lambda s: s.confidence)
