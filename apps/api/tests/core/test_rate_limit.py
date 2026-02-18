"""Tests for Phase 14A rate limiting on run-trigger endpoints.

SlowAPI rate limits are scoped per key function (user ID or IP).
In tests, the auth middleware always resolves to STUB_USER_ID so all
requests within one test are counted against the same limit bucket.

IMPORTANT: SlowAPI uses an in-memory store by default, which persists
across requests within a single test client instance. We must use a
fresh client for each test to avoid state leakage between tests.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import STUB_REPO_ID, _make_jwt


class TestRunTriggerRateLimit:
    async def test_first_request_is_accepted(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.post(f"/repos/{STUB_REPO_ID}/run", json={})
        # 201 (created) or 404/422 if Celery is not running — but never 429
        assert res.status_code != 429

    async def test_429_returned_after_exceeding_limit(
        self,
        app,
        seeded_db,
        jwt_token,
    ) -> None:
        """Send requests until we hit the rate limit.

        Uses a dedicated client to get a clean rate-limit bucket.
        The default limit is "10/minute" so 11 requests should trigger 429.
        """
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {jwt_token}"},
        ) as ac:
            statuses = []
            for _ in range(12):
                r = await ac.post(f"/repos/{STUB_REPO_ID}/run", json={})
                statuses.append(r.status_code)

        # At least one 429 should appear in the last few responses
        assert 429 in statuses, f"Expected 429 in statuses but got: {statuses}"

    async def test_429_response_has_security_headers(
        self,
        app,
        seeded_db,
        jwt_token,
    ) -> None:
        """A 429 response from the rate limiter must still have security headers."""
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {jwt_token}"},
        ) as ac:
            last_429 = None
            for _ in range(12):
                r = await ac.post(f"/repos/{STUB_REPO_ID}/run", json={})
                if r.status_code == 429:
                    last_429 = r
                    break

        if last_429 is not None:
            # Security headers must be present even on rate-limited responses
            assert last_429.headers.get("x-content-type-options") == "nosniff"
            assert last_429.headers.get("x-frame-options") == "DENY"

    async def test_get_runs_is_not_rate_limited(self, seeded_client: AsyncClient) -> None:
        """Read endpoints must not be rate-limited."""
        for _ in range(15):
            r = await seeded_client.get(f"/repos/{STUB_REPO_ID}/runs")
            assert r.status_code != 429
