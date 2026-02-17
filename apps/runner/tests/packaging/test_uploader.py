"""Unit tests for the artifact uploader.

Tests upload_artifacts() with mocked HTTP responses.
No real API calls are made.
"""

import pytest
import httpx

from runner.packaging.types import ArtifactBundle
from runner.packaging.uploader import upload_artifacts


@pytest.fixture
def sample_bundles():
    return [
        ArtifactBundle(
            filename="baseline.json",
            storage_path="repos/r1/runs/run1/baseline.json",
            content='{"is_success": true}',
            artifact_type="baseline",
        ),
        ArtifactBundle(
            filename="logs.txt",
            storage_path="repos/r1/runs/run1/logs.txt",
            content="step output here",
            artifact_type="log",
        ),
    ]


class TestUploadArtifacts:
    @pytest.mark.asyncio
    async def test_uploads_all_bundles(self, sample_bundles):
        """All bundles should be posted to the API."""
        # We'll mock httpx manually since we don't have pytest-httpx
        from unittest.mock import AsyncMock, patch, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "artifact-1"}

        with patch("runner.packaging.uploader.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await upload_artifacts(
                "http://localhost:8000",
                "proposal-123",
                sample_bundles,
            )

        assert len(results) == 2
        assert all(r.get("uploaded") for r in results)
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_upload_failure_gracefully(self, sample_bundles):
        """Failed uploads should be logged but not crash the pipeline."""
        from unittest.mock import AsyncMock, patch, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.request = MagicMock()

        with patch("runner.packaging.uploader.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=mock_response,
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await upload_artifacts(
                "http://localhost:8000",
                "proposal-123",
                sample_bundles,
            )

        assert len(results) == 2
        assert all("error" in r for r in results)
        assert all(r.get("uploaded") is False for r in results)

    @pytest.mark.asyncio
    async def test_posts_correct_payload(self, sample_bundles):
        """Verify the payload structure sent to the API."""
        from unittest.mock import AsyncMock, patch, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "artifact-1"}

        with patch("runner.packaging.uploader.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await upload_artifacts(
                "http://localhost:8000",
                "proposal-123",
                [sample_bundles[0]],
            )

        call_kwargs = mock_client.post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["proposal_id"] == "proposal-123"
        assert payload["storage_path"] == "repos/r1/runs/run1/baseline.json"
        assert payload["type"] == "baseline"
        assert "content" in payload

    @pytest.mark.asyncio
    async def test_empty_bundles_returns_empty(self):
        from unittest.mock import AsyncMock, patch

        with patch("runner.packaging.uploader.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await upload_artifacts(
                "http://localhost:8000",
                "proposal-123",
                [],
            )

        assert results == []
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """First upload succeeds, second fails."""
        from unittest.mock import AsyncMock, patch, MagicMock

        bundles = [
            ArtifactBundle(
                filename="ok.json", storage_path="repos/r/runs/1/ok.json",
                content="{}", artifact_type="baseline",
            ),
            ArtifactBundle(
                filename="fail.json", storage_path="repos/r/runs/1/fail.json",
                content="{}", artifact_type="trace",
            ),
        ]

        success_response = MagicMock()
        success_response.status_code = 201
        success_response.json.return_value = {"id": "ok-1"}

        with patch("runner.packaging.uploader.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = [
                success_response,
                httpx.ConnectError("Connection refused"),
            ]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await upload_artifacts(
                "http://localhost:8000",
                "p-1",
                bundles,
            )

        assert len(results) == 2
        assert results[0].get("uploaded") is True
        assert "error" in results[1]
