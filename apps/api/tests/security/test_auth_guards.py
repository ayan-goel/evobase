"""Security audit: every protected endpoint must reject unauthenticated requests."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import User
from tests.conftest import STUB_REPO_ID, _make_jwt

# ---------------------------------------------------------------------------
# Endpoints that MUST return 401 when called without an Authorization header.
# Format: (HTTP method, path)
# ---------------------------------------------------------------------------
PROTECTED_ENDPOINTS = [
    ("GET",  "/repos"),
    ("GET",  f"/repos/{STUB_REPO_ID}"),
    ("GET",  f"/repos/{STUB_REPO_ID}/runs"),
    ("GET",  f"/repos/{STUB_REPO_ID}/settings"),
    ("PUT",  f"/repos/{STUB_REPO_ID}/settings"),
    ("GET",  f"/artifacts/{uuid.uuid4()}/signed-url"),
    ("POST", f"/github/repos/{STUB_REPO_ID}/proposals/{uuid.uuid4()}/create-pr"),
    ("GET",  "/github/installations"),
]


class TestAuthGuards:
    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    async def test_endpoint_requires_auth(
        self,
        method: str,
        path: str,
        unauthed_client: AsyncClient,
    ) -> None:
        """Every protected endpoint must return 401 without an Authorization header."""
        response = await getattr(unauthed_client, method.lower())(path)
        assert response.status_code == 401, (
            f"{method} {path} returned {response.status_code}, expected 401"
        )

    async def test_artifacts_upload_has_no_auth_guard(
        self, unauthed_client: AsyncClient
    ) -> None:
        """/artifacts/upload is an internal runner callback — no user auth required.

        A missing proposal returns 404, not 401, confirming the endpoint is
        intentionally unprotected.
        """
        response = await unauthed_client.post(
            "/artifacts/upload",
            json={
                "proposal_id": str(uuid.uuid4()),
                "storage_path": "gs://bucket/path/artifact.json",
                "type": "proposal",
            },
        )
        assert response.status_code == 404, (
            f"Expected 404 (proposal not found), got {response.status_code}"
        )

    async def test_settings_update_wrong_user_returns_404(
        self, app, seeded_db
    ) -> None:
        """A valid JWT for a user who does not own the repo must get 404, not 200."""
        other_user_id = uuid.uuid4()
        other_user = User(id=other_user_id, email="other@example.com")
        seeded_db.add(other_user)
        await seeded_db.commit()

        token = _make_jwt(sub=other_user_id)
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as ac:
            response = await ac.put(
                f"/repos/{STUB_REPO_ID}/settings",
                json={"compute_budget_minutes": 30},
            )
        assert response.status_code == 404
