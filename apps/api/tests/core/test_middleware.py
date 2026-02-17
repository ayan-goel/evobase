"""Tests for Phase 14A middleware: request ID, security headers, CORS.

All tests use the standard `client` fixture which spins up the full app
with an in-memory SQLite database.
"""

import uuid

import pytest
from httpx import AsyncClient


class TestRequestIdMiddleware:
    async def test_response_includes_request_id_header(self, client: AsyncClient) -> None:
        res = await client.get("/health")
        assert "x-request-id" in res.headers

    async def test_generated_request_id_is_valid_uuid(self, client: AsyncClient) -> None:
        res = await client.get("/health")
        request_id = res.headers["x-request-id"]
        # Should not raise
        uuid.UUID(request_id)

    async def test_client_supplied_request_id_is_echoed_back(self, client: AsyncClient) -> None:
        my_id = str(uuid.uuid4())
        res = await client.get("/health", headers={"X-Request-ID": my_id})
        assert res.headers["x-request-id"] == my_id

    async def test_each_request_gets_a_unique_id_when_none_supplied(
        self, client: AsyncClient
    ) -> None:
        r1 = await client.get("/health")
        r2 = await client.get("/health")
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]

    async def test_request_id_present_on_404(self, client: AsyncClient) -> None:
        res = await client.get("/does-not-exist")
        assert "x-request-id" in res.headers


class TestSecurityHeadersMiddleware:
    async def test_x_content_type_options_nosniff(self, client: AsyncClient) -> None:
        res = await client.get("/health")
        assert res.headers.get("x-content-type-options") == "nosniff"

    async def test_x_frame_options_deny(self, client: AsyncClient) -> None:
        res = await client.get("/health")
        assert res.headers.get("x-frame-options") == "DENY"

    async def test_referrer_policy(self, client: AsyncClient) -> None:
        res = await client.get("/health")
        assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    async def test_xss_protection_disabled(self, client: AsyncClient) -> None:
        # Modern best-practice: disable the legacy auditor
        res = await client.get("/health")
        assert res.headers.get("x-xss-protection") == "0"

    async def test_security_headers_on_404(self, client: AsyncClient) -> None:
        res = await client.get("/nonexistent-endpoint")
        assert res.headers.get("x-content-type-options") == "nosniff"
        assert res.headers.get("x-frame-options") == "DENY"


class TestCORSMiddleware:
    async def test_cors_headers_on_options_preflight(self, client: AsyncClient) -> None:
        res = await client.options(
            "/health",
            headers={
                "Origin": "https://app.selfopt.dev",
                "Access-Control-Request-Method": "GET",
            },
        )
        # With allow_origins=["*"], the wildcard or the origin is reflected
        acao = res.headers.get("access-control-allow-origin")
        assert acao is not None

    async def test_cors_header_on_regular_request(self, client: AsyncClient) -> None:
        res = await client.get(
            "/health",
            headers={"Origin": "https://app.selfopt.dev"},
        )
        assert "access-control-allow-origin" in res.headers
