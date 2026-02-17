"""Tests for the Celery beat scheduler integration.

Tests cover:
- _is_schedule_due: cron heuristic logic with various inputs
- trigger_scheduled_runs task registration
- beat_schedule is configured on the celery app
- Celery task is discoverable
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.engine.queue import celery_app
from app.scheduling.scheduler import (
    TRIGGER_INTERVAL_SECONDS,
    _is_schedule_due,
    trigger_scheduled_runs,
)


# ---------------------------------------------------------------------------
# _is_schedule_due
# ---------------------------------------------------------------------------


class TestIsScheduleDue:
    def test_never_run_is_always_due(self) -> None:
        assert _is_schedule_due("0 2 * * *", None) is True

    def test_run_very_recently_is_not_due(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(minutes=30)
        assert _is_schedule_due("0 2 * * *", recent) is False

    def test_run_over_23_hours_ago_is_due(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(hours=24)
        assert _is_schedule_due("0 2 * * *", old) is True

    def test_malformed_schedule_falls_back_to_time_check(self) -> None:
        # Non-parseable schedule falls back to 23h heuristic
        old = datetime.now(timezone.utc) - timedelta(hours=25)
        assert _is_schedule_due("@daily", old) is True

    def test_malformed_schedule_recent_run_not_due(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(hours=2)
        assert _is_schedule_due("not-a-cron", recent) is False

    def test_every_6_hours_due_when_old(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(hours=24)
        assert _is_schedule_due("0 */6 * * *", old) is True


# ---------------------------------------------------------------------------
# Celery task registration
# ---------------------------------------------------------------------------


class TestTaskRegistration:
    def test_trigger_task_is_registered(self) -> None:
        registered = celery_app.tasks.keys()
        assert "selfopt.trigger_scheduled_runs" in registered

    def test_beat_schedule_configured(self) -> None:
        beat = celery_app.conf.beat_schedule
        assert "trigger-scheduled-runs" in beat
        entry = beat["trigger-scheduled-runs"]
        assert entry["task"] == "selfopt.trigger_scheduled_runs"
        assert entry["schedule"] == TRIGGER_INTERVAL_SECONDS

    def test_trigger_interval_is_reasonable(self) -> None:
        # Should run at most hourly (3600s) and at least every 4h
        assert 600 <= TRIGGER_INTERVAL_SECONDS <= 14400


# ---------------------------------------------------------------------------
# trigger_scheduled_runs task
# ---------------------------------------------------------------------------


class TestTriggerScheduledRuns:
    def test_task_is_celery_task(self) -> None:
        # Should be a registered Celery task, not a plain function
        assert hasattr(trigger_scheduled_runs, "delay")
        assert hasattr(trigger_scheduled_runs, "apply_async")

    def test_task_does_not_raise_on_dispatch_error(self) -> None:
        """The task swallows exceptions to avoid beat crash loops."""
        with patch(
            "app.scheduling.scheduler._dispatch_due_repos",
            side_effect=RuntimeError("DB down"),
        ):
            # Should not raise — logs and returns
            trigger_scheduled_runs.apply(args=[])

    def test_task_calls_dispatch(self) -> None:
        with patch("app.scheduling.scheduler._dispatch_due_repos") as mock_dispatch:
            trigger_scheduled_runs.apply(args=[])
            mock_dispatch.assert_called_once()
