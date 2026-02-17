"""Tests for Phase 14B Sentry integration.

Validates the before_send hook (secret scrubbing) and that init_sentry
is a no-op when no DSN is provided. No real Sentry SDK calls are made.
"""

import pytest

from app.core.sentry import _scrub_dict, _scrub_secrets, init_sentry


class TestScrubDict:
    def test_redacts_api_key_values(self) -> None:
        d = {"openai_api_key": "sk-abc123", "name": "test"}
        _scrub_dict(d)
        assert d["openai_api_key"] == "[REDACTED]"
        assert d["name"] == "test"

    def test_redacts_password_values(self) -> None:
        d = {"redis_password": "supersecret"}
        _scrub_dict(d)
        assert d["redis_password"] == "[REDACTED]"

    def test_redacts_secret_values(self) -> None:
        d = {"github_webhook_secret": "abc"}
        _scrub_dict(d)
        assert d["github_webhook_secret"] == "[REDACTED]"

    def test_redacts_token_values(self) -> None:
        d = {"access_token": "tok_abc"}
        _scrub_dict(d)
        assert d["access_token"] == "[REDACTED]"

    def test_redacts_dsn_values(self) -> None:
        d = {"sentry_dsn": "https://sentry.io/123"}
        _scrub_dict(d)
        assert d["sentry_dsn"] == "[REDACTED]"

    def test_preserves_non_sensitive_values(self) -> None:
        d = {"user_id": "abc", "status": "running"}
        _scrub_dict(d)
        assert d["user_id"] == "abc"
        assert d["status"] == "running"

    def test_recurses_into_nested_dicts(self) -> None:
        d = {"config": {"api_key": "secret123"}}
        _scrub_dict(d)
        assert d["config"]["api_key"] == "[REDACTED]"

    def test_case_insensitive_matching(self) -> None:
        d = {"API_KEY": "secret", "Secret": "value"}
        _scrub_dict(d)
        assert d["API_KEY"] == "[REDACTED]"
        assert d["Secret"] == "[REDACTED]"


class TestScrubSecrets:
    def test_scrubs_extra_dict(self) -> None:
        event = {"extra": {"anthropic_api_key": "sk-ant-xyz"}, "request": {}}
        result = _scrub_secrets(event, None)
        assert result["extra"]["anthropic_api_key"] == "[REDACTED]"

    def test_scrubs_request_data(self) -> None:
        event = {
            "extra": {},
            "request": {"data": {"password": "hunter2"}},
        }
        result = _scrub_secrets(event, None)
        assert result["request"]["data"]["password"] == "[REDACTED]"

    def test_passes_through_event_with_no_sensitive_keys(self) -> None:
        event = {
            "extra": {"user_id": "abc", "run_id": "xyz"},
            "request": {"data": {"status": "ok"}},
        }
        result = _scrub_secrets(event, None)
        assert result["extra"]["user_id"] == "abc"
        assert result["extra"]["run_id"] == "xyz"

    def test_handles_missing_extra_key(self) -> None:
        event = {"request": {}}
        # Should not raise
        result = _scrub_secrets(event, None)
        assert result is event

    def test_handles_non_dict_request_data(self) -> None:
        event = {"extra": {}, "request": {"data": "raw-body-string"}}
        # Should not raise
        result = _scrub_secrets(event, None)
        assert result is event


class TestInitSentry:
    def test_no_op_when_dsn_is_empty(self) -> None:
        # Should not raise, should not initialise SDK
        init_sentry(dsn="", environment="test")

    def test_no_op_when_dsn_is_whitespace(self) -> None:
        init_sentry(dsn="   ", environment="test")

    def test_accepts_valid_arguments_without_raising(self) -> None:
        # With a blank DSN, no SDK init happens — just a no-op
        init_sentry(dsn="", environment="development")
        init_sentry(dsn="", environment="production")
