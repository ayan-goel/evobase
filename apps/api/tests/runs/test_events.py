"""Tests for the Redis Streams + Postgres event bus."""

import json
from unittest.mock import MagicMock, call, patch

import pytest

from app.runs.events import (
    _cancel_key,
    _is_uuid,
    _stream_key,
    _task_id_key,
    get_task_id,
    is_cancelled,
    publish_event,
    set_cancel_flag,
    store_task_id,
)

RUN_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture(autouse=True)
def _reset_sync_redis():
    """Reset the module-level sync redis client between tests."""
    import app.runs.events as mod
    mod._sync_redis = None
    yield
    mod._sync_redis = None


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

class TestStreamKeys:
    def test_stream_key_format(self):
        assert _stream_key("abc-123") == "run_events:abc-123"

    def test_cancel_key_format(self):
        assert _cancel_key("abc-123") == "run_cancel:abc-123"

    def test_task_id_key_format(self):
        assert _task_id_key("abc-123") == "run_task:abc-123"


# ---------------------------------------------------------------------------
# _is_uuid
# ---------------------------------------------------------------------------

class TestIsUuid:
    def test_valid_uuid(self):
        assert _is_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_invalid_string(self):
        assert _is_uuid("1710000000000-0") is False

    def test_zero_string(self):
        assert _is_uuid("0") is False

    def test_empty_string(self):
        assert _is_uuid("") is False


# ---------------------------------------------------------------------------
# publish_event
# ---------------------------------------------------------------------------

class TestPublishEvent:
    @patch("app.runs.events._get_sync_redis")
    @patch("app.db.sync_session.get_sync_db")
    def test_publishes_to_redis_and_persists_to_postgres(
        self, mock_get_db, mock_get_redis
    ):
        # Redis mocks
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = ["1234567890-0", True]
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        # DB mocks
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_session

        result = publish_event(RUN_ID, "clone.started", "clone", {"repo": "org/repo"})

        assert result == "1234567890-0"

        # Verify Redis xadd was called
        mock_pipe.xadd.assert_called_once()
        call_args = mock_pipe.xadd.call_args
        assert call_args[0][0] == f"run_events:{RUN_ID}"
        payload = call_args[0][1]
        assert payload["type"] == "clone.started"
        assert payload["phase"] == "clone"
        assert json.loads(payload["data"]) == {"repo": "org/repo"}
        # pg_id must be a UUID included in the Redis payload for deduplication
        assert _is_uuid(payload["pg_id"])

        # Verify Redis TTL was set
        mock_pipe.expire.assert_called_once_with(
            f"run_events:{RUN_ID}", 7 * 24 * 60 * 60
        )

        # Verify Postgres persistence
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        added_row = mock_session.add.call_args[0][0]
        assert added_row.event_type == "clone.started"
        assert added_row.phase == "clone"
        assert added_row.data == {"repo": "org/repo"}
        assert added_row.stream_id == "1234567890-0"

    @patch("app.runs.events._get_sync_redis")
    @patch("app.db.sync_session.get_sync_db")
    def test_redis_failure_does_not_prevent_postgres_write(
        self, mock_get_db, mock_get_redis
    ):
        mock_pipe = MagicMock()
        mock_pipe.execute.side_effect = ConnectionError("Redis down")
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_session

        result = publish_event(RUN_ID, "clone.started", "clone")

        # Redis failed → returns empty string
        assert result == ""
        # Postgres write still attempted
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("app.runs.events._get_sync_redis")
    @patch("app.db.sync_session.get_sync_db")
    def test_postgres_failure_does_not_raise(
        self, mock_get_db, mock_get_redis
    ):
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = ["1-0", True]
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.commit.side_effect = RuntimeError("DB error")
        mock_get_db.return_value = mock_session

        # Must not raise — DB errors are best-effort
        result = publish_event(RUN_ID, "test.event", "test")
        assert result == "1-0"

    @patch("app.runs.events._get_sync_redis")
    @patch("app.db.sync_session.get_sync_db")
    def test_defaults_data_to_empty_dict(self, mock_get_db, mock_get_redis):
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = ["1-0", True]
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_session

        publish_event(RUN_ID, "test.event", "test")

        payload = mock_pipe.xadd.call_args[0][1]
        assert json.loads(payload["data"]) == {}

        added_row = mock_session.add.call_args[0][0]
        assert added_row.data == {}


# ---------------------------------------------------------------------------
# Cancel flag
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task ID
# ---------------------------------------------------------------------------

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
