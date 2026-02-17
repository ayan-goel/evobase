"""Tests for confidence scoring and signal merging.

Verifies that the orchestrator correctly computes confidence
and picks the highest-confidence signal.
"""

import json
from pathlib import Path

import pytest

from runner.detector import detect
from runner.detector.orchestrator import _pick_best
from runner.detector.types import CommandSignal


class TestPickBest:
    def test_picks_highest_confidence(self):
        signals = [
            CommandSignal(command="low", source="test", confidence=0.3),
            CommandSignal(command="high", source="test", confidence=0.9),
            CommandSignal(command="mid", source="test", confidence=0.6),
        ]
        best = _pick_best(signals)
        assert best is not None
        assert best.command == "high"

    def test_empty_list_returns_none(self):
        assert _pick_best([]) is None

    def test_single_signal(self):
        signal = CommandSignal(command="only", source="test", confidence=0.5)
        assert _pick_best([signal]) == signal

    def test_tie_returns_first(self):
        """On equal confidence, first signal (package.json) wins."""
        signals = [
            CommandSignal(command="first", source="pkg", confidence=0.9),
            CommandSignal(command="second", source="ci", confidence=0.9),
        ]
        best = _pick_best(signals)
        assert best.command == "first"


class TestOverallConfidence:
    """Test that overall confidence is the minimum of all field confidences."""

    def test_high_confidence_repo(self, tmp_path):
        """Repo with lock file + scripts = high confidence."""
        (tmp_path / "package.json").write_text(json.dumps({
            "scripts": {"build": "tsc", "test": "jest"},
            "dependencies": {"next": "15.0.0"},
        }))
        (tmp_path / "package-lock.json").write_text("{}")

        result = detect(tmp_path)
        # Lock file gives 0.95, scripts give 0.9, framework gives 0.85
        # Minimum = 0.85
        assert result.confidence >= 0.8

    def test_low_confidence_no_lock(self, tmp_path):
        """Repo with no lock file has lower confidence."""
        (tmp_path / "package.json").write_text(json.dumps({
            "scripts": {"test": "jest"},
        }))

        result = detect(tmp_path)
        # No lock file means pm confidence is 0.5, which brings the minimum down
        assert result.confidence <= 0.5

    def test_empty_dir_zero_confidence(self, tmp_path):
        """Empty directory produces zero confidence."""
        result = detect(tmp_path)
        assert result.confidence <= 0.2

    def test_confidence_rounded_to_two_decimals(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "scripts": {"test": "jest"},
        }))
        result = detect(tmp_path)
        d = result.to_dict()
        # Ensure confidence is a clean float with at most 2 decimal places
        assert d["confidence"] == round(d["confidence"], 2)


class TestEvidenceTracking:
    def test_evidence_tracks_package_manager_source(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"scripts": {}}))
        (tmp_path / "yarn.lock").write_text("")

        result = detect(tmp_path)
        pm_evidence = [e for e in result.evidence if "package_manager" in e]
        assert len(pm_evidence) == 1
        assert "yarn.lock" in pm_evidence[0]

    def test_evidence_tracks_install_cmd(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"scripts": {}}))
        (tmp_path / "yarn.lock").write_text("")

        result = detect(tmp_path)
        install_evidence = [e for e in result.evidence if "install_cmd" in e]
        assert len(install_evidence) == 1
        assert "yarn" in install_evidence[0]

    def test_evidence_tracks_framework(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "dependencies": {"express": "4.0.0"},
        }))

        result = detect(tmp_path)
        fw_evidence = [e for e in result.evidence if "framework" in e]
        assert len(fw_evidence) == 1
        assert "express" in fw_evidence[0]
