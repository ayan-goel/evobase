"""Tests for GitHub App JWT generation."""

from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.github.auth import create_app_jwt


def _generate_test_private_key() -> str:
    """Generate a valid RSA private key for testing."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return pem.decode()


TEST_PRIVATE_KEY = _generate_test_private_key()


class TestCreateAppJwt:
    @patch("app.github.auth.get_settings")
    def test_creates_valid_jwt(self, mock_settings):
        mock_settings.return_value.github_app_id = "12345"
        mock_settings.return_value.github_private_key = TEST_PRIVATE_KEY

        token = create_app_jwt()
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    @patch("app.github.auth.get_settings")
    def test_jwt_contains_correct_issuer(self, mock_settings):
        mock_settings.return_value.github_app_id = "12345"
        mock_settings.return_value.github_private_key = TEST_PRIVATE_KEY

        token = create_app_jwt()
        decoded = jwt.decode(token, options={"verify_signature": False})
        assert decoded["iss"] == "12345"

    @patch("app.github.auth.get_settings")
    def test_jwt_expiry_is_roughly_9_minutes(self, mock_settings):
        mock_settings.return_value.github_app_id = "12345"
        mock_settings.return_value.github_private_key = TEST_PRIVATE_KEY

        token = create_app_jwt()
        decoded = jwt.decode(token, options={"verify_signature": False})

        # exp - iat should be ~10 minutes (9 min + 60s backdate)
        duration = decoded["exp"] - decoded["iat"]
        assert 540 <= duration <= 600

    @patch("app.github.auth.get_settings")
    def test_missing_credentials_raises(self, mock_settings):
        mock_settings.return_value.github_app_id = ""
        mock_settings.return_value.github_private_key = ""

        with pytest.raises(ValueError, match="GitHub App credentials"):
            create_app_jwt()
