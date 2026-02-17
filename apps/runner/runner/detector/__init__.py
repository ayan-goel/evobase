"""Detector module for auto-detecting repo build/test configuration.

Public API:
    detect(repo_dir) -> DetectionResult
"""

from runner.detector.orchestrator import detect
from runner.detector.types import CommandSignal, DetectionResult

__all__ = ["detect", "CommandSignal", "DetectionResult"]
