"""Detector orchestrator — merges signals from all sources.

This is the public entry point for detection. It:
1. Runs the package.json parser
2. Runs the CI workflow parser
3. Detects the package manager from lock files
4. Detects the framework from dependencies
5. Merges signals, resolving conflicts by confidence
6. Produces a single DetectionResult with confidence + evidence
"""

import logging
from pathlib import Path

from runner.detector.ci_parser import parse_ci_workflows
from runner.detector.package_json import (
    detect_framework,
    detect_package_manager,
    get_install_command,
    parse_package_json,
)
from runner.detector.types import CommandSignal, DetectionResult

logger = logging.getLogger(__name__)


def detect(repo_dir: Path) -> DetectionResult:
    """Run full detection pipeline on a repository directory.

    Merges signals from package.json and CI workflows,
    preferring the highest-confidence signal for each category.
    """
    repo_dir = Path(repo_dir)
    result = DetectionResult()
    all_confidences: list[float] = []

    # 1. Detect package manager (highest priority: lock files)
    pm_signal = detect_package_manager(repo_dir)
    ci_signals = parse_ci_workflows(repo_dir)

    # Merge package manager signals from CI (if more confident)
    ci_pm_signals = ci_signals.pop("package_manager", [])
    best_pm = _pick_best([pm_signal] + ci_pm_signals)
    if best_pm:
        result.package_manager = best_pm.command
        result.evidence.append(f"package_manager: {best_pm.command} ({best_pm.source})")
        all_confidences.append(best_pm.confidence)

    # 2. Parse package.json scripts
    pkg_signals = parse_package_json(repo_dir)

    # 3. Merge build/test/typecheck from both sources
    for category in ("build", "test", "typecheck"):
        pkg_category_signals = pkg_signals.get(category, [])
        ci_category_signals = ci_signals.get(category, [])
        best = _pick_best(pkg_category_signals + ci_category_signals)

        if best:
            # Replace {pm} placeholder with the detected package manager
            pm = result.package_manager or "npm"
            resolved_cmd = best.command.replace("{pm}", pm)
            setattr(result, f"{category}_cmd", resolved_cmd)
            result.evidence.append(f"{category}_cmd: {resolved_cmd} ({best.source})")
            all_confidences.append(best.confidence)

    # 4. Set install command based on package manager
    pm = result.package_manager or "npm"
    result.install_cmd = get_install_command(pm)
    result.evidence.append(f"install_cmd: {result.install_cmd} (derived from {pm})")
    all_confidences.append(pm_signal.confidence if pm_signal else 0.5)

    # 5. Detect framework
    fw_signal = detect_framework(repo_dir)
    if fw_signal:
        result.framework = fw_signal.command
        result.evidence.append(f"framework: {fw_signal.command} ({fw_signal.source})")
        all_confidences.append(fw_signal.confidence)

    # 6. Compute overall confidence as the minimum across all fields
    result.confidence = min(all_confidences) if all_confidences else 0.0

    logger.info(
        "Detection complete: pm=%s framework=%s confidence=%.2f",
        result.package_manager,
        result.framework,
        result.confidence,
    )

    return result


def _pick_best(signals: list[CommandSignal]) -> CommandSignal | None:
    """Pick the signal with the highest confidence.

    Returns None if the list is empty.
    On ties, the first signal (usually package.json) wins.
    """
    if not signals:
        return None
    return max(signals, key=lambda s: s.confidence)
