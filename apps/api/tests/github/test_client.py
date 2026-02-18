"""Tests for GitHub Contents API client functions.

get_file_content, put_file_content, and delete_file are mocked at the
httpx.AsyncClient level so tests run without real network calls.
"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_response(status_code: int, json_data: dict) -> MagicMock:
    """Build a minimal mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data

    def raise_for_status():
        if status_code >= 400:
            from httpx import HTTPStatusError, Request, Response as RealResponse
            raise HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=MagicMock(status_code=status_code),
            )

    resp.raise_for_status = raise_for_status
    return resp


class TestGetFileContent:
    @pytest.mark.asyncio
    async def test_returns_decoded_content_and_sha(self):
        from app.github.client import get_file_content

        raw = base64.b64encode(b"hello world\n").decode()
        mock_resp = _make_response(200, {"content": raw, "sha": "abc123"})

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.get = AsyncMock(return_value=mock_resp)

            result = await get_file_content("tok", "owner", "repo", "src/foo.ts", "main")

        assert result is not None
        assert result["content"] == "hello world\n"
        assert result["sha"] == "abc123"

    @pytest.mark.asyncio
    async def test_returns_none_for_404(self):
        from app.github.client import get_file_content

        mock_resp = _make_response(404, {"message": "Not Found"})

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.get = AsyncMock(return_value=mock_resp)

            result = await get_file_content("tok", "owner", "repo", "missing.ts", "main")

        assert result is None

    @pytest.mark.asyncio
    async def test_passes_ref_as_query_param(self):
        from app.github.client import get_file_content

        raw = base64.b64encode(b"x").decode()
        mock_resp = _make_response(200, {"content": raw, "sha": "s"})

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.get = AsyncMock(return_value=mock_resp)

            await get_file_content("tok", "owner", "repo", "path.ts", "feature/x")

            call_kwargs = MockClient.return_value.get.call_args
            assert call_kwargs.kwargs["params"] == {"ref": "feature/x"}


class TestPutFileContent:
    @pytest.mark.asyncio
    async def test_create_new_file(self):
        from app.github.client import put_file_content

        mock_resp = _make_response(201, {"content": {"sha": "newsha"}})

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.put = AsyncMock(return_value=mock_resp)

            await put_file_content(
                "tok", "owner", "repo", "src/new.ts",
                "add file", "content here", "main",
            )

            call_kwargs = MockClient.return_value.put.call_args
            payload = call_kwargs.kwargs["json"]
            assert payload["branch"] == "main"
            assert payload["message"] == "add file"
            assert "sha" not in payload  # no current_sha for new file

    @pytest.mark.asyncio
    async def test_update_existing_file_passes_sha(self):
        from app.github.client import put_file_content

        mock_resp = _make_response(200, {"content": {"sha": "updatedsha"}})

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.put = AsyncMock(return_value=mock_resp)

            await put_file_content(
                "tok", "owner", "repo", "src/existing.ts",
                "update file", "new content", "main",
                current_sha="existingsha",
            )

            call_kwargs = MockClient.return_value.put.call_args
            payload = call_kwargs.kwargs["json"]
            assert payload["sha"] == "existingsha"

    @pytest.mark.asyncio
    async def test_content_is_base64_encoded(self):
        from app.github.client import put_file_content

        mock_resp = _make_response(200, {})

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.put = AsyncMock(return_value=mock_resp)

            await put_file_content(
                "tok", "owner", "repo", "f.ts",
                "msg", "hello\n", "main",
            )

            call_kwargs = MockClient.return_value.put.call_args
            encoded = call_kwargs.kwargs["json"]["content"]
            assert base64.b64decode(encoded) == b"hello\n"


class TestDeleteFile:
    @pytest.mark.asyncio
    async def test_calls_delete_with_sha(self):
        from app.github.client import delete_file

        mock_resp = _make_response(200, {"commit": {"sha": "del"}})

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.request = AsyncMock(return_value=mock_resp)

            await delete_file(
                "tok", "owner", "repo", "src/old.ts",
                "remove unused file", "fileSHA", "main",
            )

            call_kwargs = MockClient.return_value.request.call_args
            assert call_kwargs.args[0] == "DELETE"
            payload = call_kwargs.kwargs["json"]
            assert payload["sha"] == "fileSHA"
            assert payload["branch"] == "main"
            assert payload["message"] == "remove unused file"
