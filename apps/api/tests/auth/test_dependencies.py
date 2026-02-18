"""Tests for JWT-based authentication dependency."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import STUB_USER_ID, TEST_JWT_SECRET, _make_jwt


class TestGetCurrentUserViaAPI:
    """Exercise get_current_user through the /repos endpoint which depends on it."""

    async def test_valid_jwt_returns_user_uuid(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.get("/repos")
        assert res.status_code == 200

    async def test_expired_jwt_raises_401(self, app, seeded_db) -> None:
        from httpx import ASGITransport, AsyncClient as HC

        token = _make_jwt(expired=True)
        transport = ASGITransport(app=app)
        async with HC(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as ac:
            res = await ac.get("/repos")
            assert res.status_code == 401

    async def test_missing_authorization_header_raises_401(
        self, unauthed_client: AsyncClient
    ) -> None:
        res = await unauthed_client.get("/repos")
        assert res.status_code == 401

    async def test_malformed_token_raises_401(self, app, seeded_db) -> None:
        from httpx import ASGITransport, AsyncClient as HC

        transport = ASGITransport(app=app)

        for bad_header in [
            "garbage-no-bearer-prefix",
            "Bearer ",
            "Bearer not.a.valid.jwt",
        ]:
            async with HC(
                transport=transport,
                base_url="http://test",
                headers={"Authorization": bad_header},
            ) as ac:
                res = await ac.get("/repos")
                assert res.status_code == 401, f"Expected 401 for header: {bad_header!r}"

    async def test_wrong_audience_raises_401(self, app, seeded_db) -> None:
        from httpx import ASGITransport, AsyncClient as HC

        token = _make_jwt(audience="wrong-audience")
        transport = ASGITransport(app=app)
        async with HC(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as ac:
            res = await ac.get("/repos")
            assert res.status_code == 401

    async def test_first_login_upserts_user(self, app, db_session) -> None:
        """A JWT with an unknown UUID should auto-create a user row."""
        from httpx import ASGITransport, AsyncClient as HC
        from sqlalchemy import select
        from app.db.models import User

        new_user_id = uuid.uuid4()
        token = _make_jwt(sub=new_user_id, email="new@example.com")
        transport = ASGITransport(app=app)
        async with HC(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as ac:
            res = await ac.get("/repos")
            assert res.status_code == 200

        result = await db_session.execute(
            select(User).where(User.id == new_user_id)
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.email == "new@example.com"
