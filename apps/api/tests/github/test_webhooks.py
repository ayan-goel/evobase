"""Tests for GitHub webhook signature verification and event parsing."""

import hashlib
import hmac
from unittest.mock import patch

import pytest

from app.github.webhooks import parse_installation_event, verify_webhook_signature


MOCK_SECRET = "test-webhook-secret-123"


class TestVerifyWebhookSignature:
    """Webhook signatures use HMAC-SHA256 as specified by GitHub."""

    def _sign(self, payload: bytes) -> str:
        """Generate a valid signature for test payloads."""
        sig = hmac.new(
            MOCK_SECRET.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={sig}"

    @patch("app.github.webhooks.get_settings")
    def test_valid_signature_passes(self, mock_settings):
        mock_settings.return_value.github_webhook_secret = MOCK_SECRET
        payload = b'{"action":"created"}'
        signature = self._sign(payload)

        assert verify_webhook_signature(payload, signature) is True

    @patch("app.github.webhooks.get_settings")
    def test_invalid_signature_fails(self, mock_settings):
        mock_settings.return_value.github_webhook_secret = MOCK_SECRET
        payload = b'{"action":"created"}'

        assert verify_webhook_signature(payload, "sha256=bad") is False

    @patch("app.github.webhooks.get_settings")
    def test_missing_prefix_fails(self, mock_settings):
        mock_settings.return_value.github_webhook_secret = MOCK_SECRET
        payload = b'{"action":"created"}'

        assert verify_webhook_signature(payload, "no-prefix") is False

    @patch("app.github.webhooks.get_settings")
    def test_empty_signature_fails(self, mock_settings):
        mock_settings.return_value.github_webhook_secret = MOCK_SECRET

        assert verify_webhook_signature(b"body", "") is False

    @patch("app.github.webhooks.get_settings")
    def test_tampered_payload_fails(self, mock_settings):
        """Changing the payload after signing must fail verification."""
        mock_settings.return_value.github_webhook_secret = MOCK_SECRET
        original = b'{"action":"created"}'
        signature = self._sign(original)
        tampered = b'{"action":"deleted"}'

        assert verify_webhook_signature(tampered, signature) is False

    @patch("app.github.webhooks.get_settings")
    def test_missing_secret_raises(self, mock_settings):
        mock_settings.return_value.github_webhook_secret = ""
        with pytest.raises(ValueError, match="GITHUB_WEBHOOK_SECRET"):
            verify_webhook_signature(b"body", "sha256=abc")


class TestParseInstallationEvent:
    def test_parse_created_event(self):
        payload = {
            "action": "created",
            "installation": {
                "id": 12345,
                "account": {"login": "myorg", "id": 99},
            },
            "repositories": [
                {"id": 1, "full_name": "myorg/repo1", "name": "repo1"},
                {"id": 2, "full_name": "myorg/repo2", "name": "repo2"},
            ],
        }
        result = parse_installation_event(payload)

        assert result["action"] == "created"
        assert result["installation_id"] == 12345
        assert result["account_login"] == "myorg"
        assert len(result["repositories"]) == 2
        assert result["repositories"][0]["full_name"] == "myorg/repo1"

    def test_parse_deleted_event(self):
        payload = {
            "action": "deleted",
            "installation": {
                "id": 12345,
                "account": {"login": "myorg", "id": 99},
            },
            "repositories": [],
        }
        result = parse_installation_event(payload)
        assert result["action"] == "deleted"
        assert result["repositories"] == []

    def test_parse_missing_fields_gracefully(self):
        """Handles payloads with missing optional fields without crashing."""
        result = parse_installation_event({})
        assert result["action"] == ""
        assert result["installation_id"] is None
