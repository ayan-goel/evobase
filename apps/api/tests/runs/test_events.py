"""Tests for the Redis Streams event bus."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.runs.events import (
    _cancel_key,
    _stream_key,
    _task_id_key,
    get_task_id,
    is_cancelled,
    publish_event,
    set_cancel_flag,
    store_task_id,
)


@pytest.fixture(autouse=True)
def _reset_sync_redis():
    """Reset the module-level sync redis client between tests."""
    import app.runs.events as mod
    mod._sync_redis = None
    yield
    mod._sync_redis = None


class TestStreamKeys:
    def test_stream_key_format(self):
        assert _stream_key("abc-123") == "run_events:abc-123"

    def test_cancel_key_format(self):
        assert _cancel_key("abc-123") == "run_cancel:abc-123"

    def test_task_id_key_format(self):
        assert _task_id_key("abc-123") == "run_task:abc-123"


class TestPublishEvent:
    @patch("app.runs.events._get_sync_redis")
    def test_publishes_event_to_stream(self, mock_get_redis):
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = ["1234567890-0", True]
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        result = publish_event("run-1", "clone.started", "clone", {"repo": "org/repo"})

        assert result == "1234567890-0"
        mock_pipe.xadd.assert_called_once()
        call_args = mock_pipe.xadd.call_args
        assert call_args[0][0] == "run_events:run-1"
        payload = call_args[0][1]
        assert payload["type"] == "clone.started"
        assert payload["phase"] == "clone"
        assert json.loads(payload["data"]) == {"repo": "org/repo"}

    @patch("app.runs.events._get_sync_redis")
    def test_publish_handles_redis_error_gracefully(self, mock_get_redis):
        mock_pipe = MagicMock()
        mock_pipe.execute.side_effect = ConnectionError("Redis down")
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        result = publish_event("run-1", "clone.started", "clone")
        assert result == ""

    @patch("app.runs.events._get_sync_redis")
    def test_publish_defaults_data_to_empty_dict(self, mock_get_redis):
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = ["1-0", True]
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        publish_event("run-1", "test.event", "test")

        payload = mock_pipe.xadd.call_args[0][1]
        assert json.loads(payload["data"]) == {}


class TestCancelFlag:
    @patch("app.runs.events._get_sync_redis")
    def test_set_cancel_flag(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        set_cancel_flag("run-1")

        mock_redis.set.assert_called_once_with("run_cancel:run-1", "1", ex=3600)

    @patch("app.runs.events._get_sync_redis")
    def test_is_cancelled_returns_true_when_set(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1
        mock_get_redis.return_value = mock_redis

        assert is_cancelled("run-1") is True

    @patch("app.runs.events._get_sync_redis")
    def test_is_cancelled_returns_false_when_not_set(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0
        mock_get_redis.return_value = mock_redis

        assert is_cancelled("run-1") is False


class TestTaskId:
    @patch("app.runs.events._get_sync_redis")
    def test_store_and_get_task_id(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        store_task_id("run-1", "celery-task-abc")
        mock_redis.set.assert_called_once_with("run_task:run-1", "celery-task-abc", ex=7200)

        mock_redis.get.return_value = "celery-task-abc"
        assert get_task_id("run-1") == "celery-task-abc"

    @patch("app.runs.events._get_sync_redis")
    def test_get_task_id_returns_none_when_missing(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis

        assert get_task_id("run-1") is None
