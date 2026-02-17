"""Tests for Phase 14C Supabase signed URL generation.

Validates path traversal guard and graceful fallback behaviour.
Supabase client is mocked so tests work without real credentials.
"""

import pytest

from app.artifacts.storage import _validate_path, generate_signed_url


class TestValidatePath:
    def test_rejects_dotdot_traversal(self) -> None:
        with pytest.raises(ValueError, match="traversal"):
            _validate_path("../etc/passwd")

    def test_rejects_embedded_dotdot(self) -> None:
        with pytest.raises(ValueError, match="traversal"):
            _validate_path("runs/../../secrets")

    def test_rejects_null_byte(self) -> None:
        with pytest.raises(ValueError, match="null byte"):
            _validate_path("runs/abc\x00.patch")

    def test_rejects_empty_path(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _validate_path("")

    def test_accepts_valid_path(self) -> None:
        _validate_path("runs/abc123/diff.patch")

    def test_accepts_deep_valid_path(self) -> None:
        _validate_path("repos/owner/name/runs/abc/artifacts/output.json")

    def test_accepts_path_with_dots_in_filename(self) -> None:
        # A single dot in filename (not "..") is valid
        _validate_path("runs/abc123/result.v2.json")


class TestGenerateSignedUrl:
    async def test_returns_none_when_supabase_key_not_configured(
        self, monkeypatch
    ) -> None:
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")
        result = await generate_signed_url("runs/abc/diff.patch")
        assert result is None

    async def test_raises_on_path_traversal(self) -> None:
        with pytest.raises(ValueError, match="traversal"):
            await generate_signed_url("../etc/passwd")

    async def test_raises_on_null_byte_in_path(self) -> None:
        with pytest.raises(ValueError, match="null byte"):
            await generate_signed_url("runs/abc\x00.patch")

    async def test_calls_supabase_client_when_key_is_set(
        self, monkeypatch
    ) -> None:
        """When a service key is present, it calls the Supabase storage API."""
        import sys
        from unittest.mock import MagicMock

        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key-abc")
        monkeypatch.setenv("SUPABASE_URL", "https://xyz.supabase.co")

        mock_bucket = MagicMock()
        mock_bucket.create_signed_url.return_value = {
            "signedURL": "https://xyz.supabase.co/storage/v1/sign/artifacts/runs/abc/diff.patch?token=tok"
        }

        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket

        mock_client = MagicMock()
        mock_client.storage = mock_storage

        # Inject a fake `supabase` module so the lazy `from supabase import create_client`
        # inside generate_signed_url returns our mock.
        mock_supabase_module = MagicMock()
        mock_supabase_module.create_client.return_value = mock_client
        monkeypatch.setitem(sys.modules, "supabase", mock_supabase_module)

        result = await generate_signed_url("runs/abc/diff.patch", expires_in=600)

        assert result == "https://xyz.supabase.co/storage/v1/sign/artifacts/runs/abc/diff.patch?token=tok"
        mock_bucket.create_signed_url.assert_called_once_with("runs/abc/diff.patch", 600)

    async def test_returns_none_when_supabase_raises(self, monkeypatch) -> None:
        """Supabase API errors should be caught and return None, not crash."""
        import sys
        from unittest.mock import MagicMock

        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key-abc")

        mock_supabase_module = MagicMock()
        mock_supabase_module.create_client.side_effect = RuntimeError("Connection refused")
        monkeypatch.setitem(sys.modules, "supabase", mock_supabase_module)

        result = await generate_signed_url("runs/abc/diff.patch")

        assert result is None
