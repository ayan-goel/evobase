"""Ruby ecosystem detector.

Entry point: detect_ruby(repo_dir) -> DetectionResult
"""

from pathlib import Path

from runner.detector.ruby.defaults import (
    DEFAULT_TEST_CMD,
    FRAMEWORK_TEST_CMDS,
    INSTALL_CMD,
)
from runner.detector.ruby import gemfile
from runner.detector.types import CommandSignal, DetectionResult


def detect_ruby(repo_dir: Path) -> DetectionResult:
    """Run full Ruby detection on a repository directory."""
    result = DetectionResult(language="ruby")
    all_confidences: list[float] = []

    # 1. Package manager — always bundler for Ruby
    result.package_manager = "bundler"
    result.install_cmd = INSTALL_CMD
    result.evidence.append("install_cmd: bundle install (derived from bundler)")

    # 2. Framework
    fw_signal = gemfile.detect_framework(repo_dir)
    if fw_signal:
        result.framework = fw_signal.command
        result.evidence.append(f"framework: {fw_signal.command} ({fw_signal.source})")
        all_confidences.append(fw_signal.confidence)

    # 3. Test command — try to detect from Gemfile, fall back to framework defaults
    test_signal = gemfile.detect_test_framework(repo_dir)
    if test_signal:
        result.test_cmd = test_signal.command
        result.evidence.append(f"test_cmd: {test_signal.command} ({test_signal.source})")
        all_confidences.append(test_signal.confidence)
    else:
        framework = result.framework
        result.test_cmd = FRAMEWORK_TEST_CMDS.get(framework or "", DEFAULT_TEST_CMD)
        result.evidence.append(
            f"test_cmd: {result.test_cmd} (default for {framework or 'ruby'})"
        )

    result.confidence = min(all_confidences) if all_confidences else 0.5
    return result


def _pick_best(signals: list[CommandSignal]) -> CommandSignal | None:
    if not signals:
        return None
    return max(signals, key=lambda s: s.confidence)
