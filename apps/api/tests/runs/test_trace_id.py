"""Tests for trace_id propagation on Run creation (Phase 14B).

The trace_id on a Run ties it to the originating HTTP request, making
all Celery worker logs for that run greppable by request ID.
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import STUB_REPO_ID


class TestTraceIdOnRunCreation:
    async def test_run_has_trace_id_after_creation(
        self, seeded_client: AsyncClient
    ) -> None:
        """Run created with a request ID header gets that ID as trace_id."""
        my_request_id = str(uuid.uuid4())
        res = await seeded_client.post(
            f"/repos/{STUB_REPO_ID}/run",
            json={},
            headers={"X-Request-ID": my_request_id},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["trace_id"] == my_request_id

    async def test_trace_id_generated_when_no_request_id_header(
        self, seeded_client: AsyncClient
    ) -> None:
        """Run created without a request ID header still gets a trace_id."""
        res = await seeded_client.post(
            f"/repos/{STUB_REPO_ID}/run",
            json={},
        )
        assert res.status_code == 201
        data = res.json()
        # trace_id must be set (non-null, non-empty)
        assert data["trace_id"]
        # Must be a valid UUID
        uuid.UUID(data["trace_id"])

    async def test_trace_id_matches_response_request_id_header(
        self, seeded_client: AsyncClient
    ) -> None:
        """The trace_id in the response body equals the X-Request-ID response header."""
        res = await seeded_client.post(
            f"/repos/{STUB_REPO_ID}/run",
            json={},
        )
        assert res.status_code == 201
        body_trace_id = res.json()["trace_id"]
        header_request_id = res.headers.get("x-request-id")
        assert body_trace_id == header_request_id

    async def test_different_requests_get_different_trace_ids(
        self, seeded_client: AsyncClient
    ) -> None:
        """Two separate run creations get distinct trace IDs."""
        res1 = await seeded_client.post(f"/repos/{STUB_REPO_ID}/run", json={})
        res2 = await seeded_client.post(f"/repos/{STUB_REPO_ID}/run", json={})
        assert res1.status_code == 201
        assert res2.status_code == 201
        assert res1.json()["trace_id"] != res2.json()["trace_id"]

    async def test_trace_id_in_run_response_schema(
        self, seeded_client: AsyncClient
    ) -> None:
        """RunResponse schema includes trace_id field."""
        res = await seeded_client.post(f"/repos/{STUB_REPO_ID}/run", json={})
        assert res.status_code == 201
        data = res.json()
        assert "trace_id" in data
