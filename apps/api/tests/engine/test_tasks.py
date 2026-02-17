"""Unit tests for Celery task definitions.

Tests task execution logic by calling the function directly (no broker).
The RunService is mocked to verify orchestration flow.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.engine.tasks import execute_run


class TestExecuteRunTask:
    """Test the execute_run Celery task logic."""

    @patch("app.engine.tasks.RunService")
    def test_execute_run_happy_path(self, mock_service_cls):
        """Successful run: queued -> running -> completed."""
        mock_service = MagicMock()
        mock_service.execute_full_pipeline.return_value = {
            "baseline_completed": True,
            "run_id": "test-run-id",
        }
        mock_service_cls.return_value = mock_service

        result = execute_run("test-run-id")

        mock_service.transition_to_running.assert_called_once_with("test-run-id")
        mock_service.execute_full_pipeline.assert_called_once_with("test-run-id")
        mock_service.transition_to_completed.assert_called_once_with(
            "test-run-id",
            {"baseline_completed": True, "run_id": "test-run-id"},
        )
        mock_service.transition_to_failed.assert_not_called()
        assert result["status"] == "completed"
        assert result["run_id"] == "test-run-id"

    @patch("app.engine.tasks.RunService")
    def test_execute_run_failure_transitions_to_failed(self, mock_service_cls):
        """When pipeline execution raises, the run transitions to failed."""
        mock_service = MagicMock()
        mock_service.execute_full_pipeline.side_effect = RuntimeError("sandbox crashed")
        mock_service_cls.return_value = mock_service

        result = execute_run("test-run-id")

        mock_service.transition_to_running.assert_called_once_with("test-run-id")
        mock_service.execute_full_pipeline.assert_called_once_with("test-run-id")
        mock_service.transition_to_failed.assert_called_once_with(
            "test-run-id", "sandbox crashed"
        )
        mock_service.transition_to_completed.assert_not_called()
        assert result["status"] == "failed"
        assert "sandbox crashed" in result["error"]

    @patch("app.engine.tasks.RunService")
    def test_execute_run_transition_failure(self, mock_service_cls):
        """When transition_to_running raises, the run is marked failed."""
        mock_service = MagicMock()
        mock_service.transition_to_running.side_effect = ValueError(
            "Invalid state transition"
        )
        mock_service_cls.return_value = mock_service

        result = execute_run("test-run-id")

        mock_service.transition_to_running.assert_called_once_with("test-run-id")
        mock_service.execute_full_pipeline.assert_not_called()
        mock_service.transition_to_failed.assert_called_once()
        assert result["status"] == "failed"

    @patch("app.engine.tasks.RunService")
    def test_execute_run_returns_correct_structure(self, mock_service_cls):
        """Verify the return dict matches the expected shape."""
        mock_service = MagicMock()
        mock_service.execute_full_pipeline.return_value = {"baseline_completed": True}
        mock_service_cls.return_value = mock_service

        result = execute_run("abc-123")

        assert "run_id" in result
        assert "status" in result
        assert result["run_id"] == "abc-123"
