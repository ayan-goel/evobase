"""Detector orchestrator — probes language and routes to the right detector.

Detection flow:
1. Probe the repository root for language-identifying files (priority order).
2. Route to the appropriate language-specific detector.
3. Merge CI workflow signals for build/test/typecheck (language-agnostic).
4. Produce a single DetectionResult with language + framework + commands.

Language priority (first match wins):
  Cargo.toml  → Rust
  go.mod      → Go
  pyproject.toml / requirements.txt → Python
  Gemfile                           → Ruby
  pom.xml / build.gradle            → JVM (Java/Kotlin)
  CMakeLists.txt / Makefile+native  → C/C++
  package.json (default)            → JavaScript / TypeScript
"""

import logging
from pathlib import Path

from runner.detector.ci_parser import infer_command_ecosystems, parse_ci_workflows
from runner.detector.package_json import (
    detect_framework,
    detect_package_manager,
    get_install_command,
    parse_package_json,
)
from runner.detector.types import CommandSignal, DetectionResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def detect(repo_dir: Path) -> DetectionResult:
    """Run the full detection pipeline on a repository directory.

    Probes for language, routes to the appropriate detector, then merges
    CI workflow signals. Returns a single DetectionResult.
    """
    repo_dir = Path(repo_dir)

    if (repo_dir / "Cargo.toml").exists():
        return _detect_rust(repo_dir)
    if (repo_dir / "go.mod").exists():
        return _detect_go(repo_dir)
    if (repo_dir / "pyproject.toml").exists() or (repo_dir / "requirements.txt").exists():
        return _detect_python(repo_dir)
    if (repo_dir / "Gemfile").exists():
        return _detect_ruby(repo_dir)
    if (
        (repo_dir / "pom.xml").exists()
        or (repo_dir / "build.gradle").exists()
        or (repo_dir / "build.gradle.kts").exists()
    ):
        return _detect_jvm(repo_dir)
    if _is_cpp_repo(repo_dir):
        return _detect_cpp(repo_dir)
    return _detect_js(repo_dir)


# ---------------------------------------------------------------------------
# Language-specific detection helpers
# ---------------------------------------------------------------------------

def _detect_js(repo_dir: Path) -> DetectionResult:
    """Detect a JavaScript / TypeScript project via package.json."""
    result = DetectionResult(language="javascript")
    all_confidences: list[float] = []

    pm_signal = detect_package_manager(repo_dir)
    ci_signals = parse_ci_workflows(repo_dir)

    ci_pm_signals = [
        signal
        for signal in ci_signals.pop("package_manager", [])
        if signal.command in {"npm", "pnpm", "yarn", "bun"}
    ]
    best_pm = _pick_best([pm_signal] + ci_pm_signals)
    if best_pm:
        result.package_manager = best_pm.command
        result.evidence.append(f"package_manager: {best_pm.command} ({best_pm.source})")
        all_confidences.append(best_pm.confidence)

    pkg_signals = parse_package_json(repo_dir)

    for category in ("build", "test", "typecheck"):
        compatible_ci = _filter_compatible_ci_signals(
            language="javascript",
            signals=ci_signals.get(category, []),
        )
        best = _pick_best(pkg_signals.get(category, []) + compatible_ci)
        if best:
            pm = result.package_manager or "npm"
            resolved_cmd = best.command.replace("{pm}", pm)
            setattr(result, f"{category}_cmd", resolved_cmd)
            result.evidence.append(f"{category}_cmd: {resolved_cmd} ({best.source})")
            all_confidences.append(best.confidence)

    pm = result.package_manager or "npm"
    result.install_cmd = get_install_command(pm)
    result.evidence.append(f"install_cmd: {result.install_cmd} (derived from {pm})")
    all_confidences.append(pm_signal.confidence if pm_signal else 0.5)

    fw_signal = detect_framework(repo_dir)
    if fw_signal:
        result.framework = fw_signal.command
        result.evidence.append(f"framework: {fw_signal.command} ({fw_signal.source})")
        all_confidences.append(fw_signal.confidence)

    result.confidence = min(all_confidences) if all_confidences else 0.0
    _log_result(result)
    return result


def _detect_python(repo_dir: Path) -> DetectionResult:
    """Detect a Python project via pyproject.toml / requirements.txt."""
    from runner.detector.python import detect_python
    result = detect_python(repo_dir)

    ci_signals = parse_ci_workflows(repo_dir)
    ci_signals.pop("package_manager", None)

    all_confidences: list[float] = [result.confidence] if result.confidence else []

    for category in ("build", "test", "typecheck"):
        ci_best = _pick_best(
            _filter_compatible_ci_signals(
                language="python",
                signals=ci_signals.get(category, []),
            )
        )
        if ci_best and getattr(result, f"{category}_cmd") is None:
            setattr(result, f"{category}_cmd", ci_best.command)
            result.evidence.append(f"{category}_cmd: {ci_best.command} ({ci_best.source})")
            all_confidences.append(ci_best.confidence)

    if all_confidences:
        result.confidence = min(all_confidences)

    _log_result(result)
    return result


def _detect_go(repo_dir: Path) -> DetectionResult:
    """Detect a Go project via go.mod."""
    from runner.detector.go import detect_go
    result = detect_go(repo_dir)

    ci_signals = parse_ci_workflows(repo_dir)
    ci_signals.pop("package_manager", None)

    all_confidences: list[float] = [result.confidence] if result.confidence else []

    for category in ("build", "test", "typecheck"):
        ci_best = _pick_best(
            _filter_compatible_ci_signals(
                language="go",
                signals=ci_signals.get(category, []),
            )
        )
        if ci_best and getattr(result, f"{category}_cmd") is None:
            setattr(result, f"{category}_cmd", ci_best.command)
            result.evidence.append(f"{category}_cmd: {ci_best.command} ({ci_best.source})")
            all_confidences.append(ci_best.confidence)

    if all_confidences:
        result.confidence = min(all_confidences)

    _log_result(result)
    return result


def _detect_ruby(repo_dir: Path) -> DetectionResult:
    """Detect a Ruby project via Gemfile."""
    from runner.detector.ruby import detect_ruby
    result = detect_ruby(repo_dir)

    ci_signals = parse_ci_workflows(repo_dir)
    ci_signals.pop("package_manager", None)

    all_confidences: list[float] = [result.confidence] if result.confidence else []

    for category in ("build", "test", "typecheck"):
        ci_best = _pick_best(
            _filter_compatible_ci_signals(
                language="ruby",
                signals=ci_signals.get(category, []),
            )
        )
        if ci_best and getattr(result, f"{category}_cmd") is None:
            setattr(result, f"{category}_cmd", ci_best.command)
            result.evidence.append(f"{category}_cmd: {ci_best.command} ({ci_best.source})")
            all_confidences.append(ci_best.confidence)

    if all_confidences:
        result.confidence = min(all_confidences)

    _log_result(result)
    return result


def _detect_jvm(repo_dir: Path) -> DetectionResult:
    """Detect a JVM project via pom.xml or build.gradle."""
    from runner.detector.jvm import detect_jvm
    result = detect_jvm(repo_dir)

    ci_signals = parse_ci_workflows(repo_dir)
    ci_signals.pop("package_manager", None)

    all_confidences: list[float] = [result.confidence] if result.confidence else []

    for category in ("build", "test", "typecheck"):
        ci_best = _pick_best(
            _filter_compatible_ci_signals(
                language="java",
                signals=ci_signals.get(category, []),
            )
        )
        if ci_best and getattr(result, f"{category}_cmd") is None:
            setattr(result, f"{category}_cmd", ci_best.command)
            result.evidence.append(f"{category}_cmd: {ci_best.command} ({ci_best.source})")
            all_confidences.append(ci_best.confidence)

    if all_confidences:
        result.confidence = min(all_confidences)

    _log_result(result)
    return result


def _detect_rust(repo_dir: Path) -> DetectionResult:
    """Detect a Rust project via Cargo.toml."""
    from runner.detector.rust import detect_rust
    result = detect_rust(repo_dir)

    ci_signals = parse_ci_workflows(repo_dir)
    ci_signals.pop("package_manager", None)

    all_confidences: list[float] = [result.confidence] if result.confidence else []

    for category in ("build", "test", "typecheck"):
        ci_best = _pick_best(
            _filter_compatible_ci_signals(
                language="rust",
                signals=ci_signals.get(category, []),
            )
        )
        if ci_best and getattr(result, f"{category}_cmd") is None:
            setattr(result, f"{category}_cmd", ci_best.command)
            result.evidence.append(f"{category}_cmd: {ci_best.command} ({ci_best.source})")
            all_confidences.append(ci_best.confidence)

    if all_confidences:
        result.confidence = min(all_confidences)

    _log_result(result)
    return result


def _detect_cpp(repo_dir: Path) -> DetectionResult:
    """Detect a C/C++ project via CMakeLists.txt or Makefile markers."""
    from runner.detector.cpp import detect_cpp
    result = detect_cpp(repo_dir)

    ci_signals = parse_ci_workflows(repo_dir)
    ci_signals.pop("package_manager", None)

    all_confidences: list[float] = [result.confidence] if result.confidence else []

    for category in ("build", "test", "typecheck"):
        ci_best = _pick_best(
            _filter_compatible_ci_signals(
                language="cpp",
                signals=ci_signals.get(category, []),
            )
        )
        if ci_best and getattr(result, f"{category}_cmd") is None:
            setattr(result, f"{category}_cmd", ci_best.command)
            result.evidence.append(f"{category}_cmd: {ci_best.command} ({ci_best.source})")
            all_confidences.append(ci_best.confidence)

    if all_confidences:
        result.confidence = min(all_confidences)

    _log_result(result)
    return result


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _pick_best(signals: list[CommandSignal]) -> CommandSignal | None:
    """Pick the signal with the highest confidence.

    Returns None if the list is empty.
    On ties, the first signal wins.
    """
    if not signals:
        return None
    return max(signals, key=lambda s: s.confidence)


def _is_cpp_repo(repo_dir: Path) -> bool:
    if (repo_dir / "CMakeLists.txt").exists():
        return True
    if not (repo_dir / "Makefile").exists():
        return False
    return _has_native_source_markers(repo_dir)


def _has_native_source_markers(repo_dir: Path) -> bool:
    extensions = (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx")
    top_level_candidates = [repo_dir] + [
        repo_dir / name for name in ("src", "source", "cpp", "csrc", "native", "include")
    ]
    for base_dir in top_level_candidates:
        if not base_dir.exists() or not base_dir.is_dir():
            continue
        for path in base_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in extensions:
                return True
    return False


def _log_result(result: DetectionResult) -> None:
    logger.info(
        "Detection complete: language=%s pm=%s framework=%s confidence=%.2f",
        result.language,
        result.package_manager,
        result.framework,
        result.confidence,
    )


def _filter_compatible_ci_signals(
    language: str,
    signals: list[CommandSignal],
) -> list[CommandSignal]:
    """Keep CI signals that appear compatible with the detected language."""
    return [signal for signal in signals if _is_signal_compatible(language, signal)]


def _is_signal_compatible(language: str, signal: CommandSignal) -> bool:
    ecosystems = infer_command_ecosystems(signal.command)
    if not ecosystems:
        # Generic commands (e.g. make test) are allowed for all languages.
        return True
    normalized_language = language.lower()
    if normalized_language == "java":
        return "java" in ecosystems
    return normalized_language in ecosystems
