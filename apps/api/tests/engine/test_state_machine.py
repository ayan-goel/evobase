"""Unit tests for the run state machine.

Validates all legal transitions and rejects illegal ones.
The state machine is the safety net for run orchestration — every
transition must be explicit and validated.
"""

import pytest

from app.runs.service import VALID_TRANSITIONS, validate_transition


class TestValidateTransition:
    """Exhaustive tests for the validate_transition guard."""

    def test_queued_to_running_allowed(self):
        validate_transition("queued", "running")

    def test_running_to_completed_allowed(self):
        validate_transition("running", "completed")

    def test_running_to_failed_allowed(self):
        validate_transition("running", "failed")

    def test_queued_to_completed_rejected(self):
        with pytest.raises(ValueError, match="Invalid run state transition"):
            validate_transition("queued", "completed")

    def test_queued_to_failed_rejected(self):
        with pytest.raises(ValueError, match="Invalid run state transition"):
            validate_transition("queued", "failed")

    def test_completed_to_running_rejected(self):
        """Terminal states have no outgoing transitions."""
        with pytest.raises(ValueError, match="Invalid run state transition"):
            validate_transition("completed", "running")

    def test_completed_to_failed_rejected(self):
        with pytest.raises(ValueError, match="Invalid run state transition"):
            validate_transition("completed", "failed")

    def test_failed_to_running_rejected(self):
        with pytest.raises(ValueError, match="Invalid run state transition"):
            validate_transition("failed", "running")

    def test_failed_to_completed_rejected(self):
        with pytest.raises(ValueError, match="Invalid run state transition"):
            validate_transition("failed", "completed")

    def test_running_to_queued_rejected(self):
        """Backward transitions are never allowed."""
        with pytest.raises(ValueError, match="Invalid run state transition"):
            validate_transition("running", "queued")

    def test_completed_to_queued_rejected(self):
        with pytest.raises(ValueError, match="Invalid run state transition"):
            validate_transition("completed", "queued")

    def test_unknown_state_rejected(self):
        with pytest.raises(ValueError, match="Invalid run state transition"):
            validate_transition("unknown", "running")

    def test_same_state_transition_rejected(self):
        """Transitioning to the same state is not allowed."""
        with pytest.raises(ValueError, match="Invalid run state transition"):
            validate_transition("queued", "queued")

        with pytest.raises(ValueError, match="Invalid run state transition"):
            validate_transition("running", "running")


class TestValidTransitionsMap:
    """Verify the transition map is complete and correct."""

    def test_queued_has_one_outgoing(self):
        assert VALID_TRANSITIONS["queued"] == {"running"}

    def test_running_has_two_outgoing(self):
        assert VALID_TRANSITIONS["running"] == {"completed", "failed"}

    def test_completed_is_terminal(self):
        assert "completed" not in VALID_TRANSITIONS

    def test_failed_is_terminal(self):
        assert "failed" not in VALID_TRANSITIONS
