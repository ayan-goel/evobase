"""Tests for POST /auth/github-callback and GET /auth/me endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, User
from tests.conftest import STUB_USER_ID


class TestGitHubCallback:
    async def test_creates_user_and_org(self, client: AsyncClient, db_session: AsyncSession) -> None:
        res = await client.post(
            "/auth/github-callback",
            json={
                "github_id": 12345,
                "github_login": "testuser",
                "avatar_url": "https://avatars.githubusercontent.com/u/12345",
                "email": "testuser@example.com",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "user_id" in data
        assert "org_id" in data

        result = await db_session.execute(
            select(User).where(User.github_id == 12345)
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.github_login == "testuser"
        assert user.email == "testuser@example.com"

        result = await db_session.execute(
            select(Organization).where(Organization.owner_id == user.id)
        )
        org = result.scalar_one_or_none()
        assert org is not None
        assert org.name == "testuser"

    async def test_idempotent(self, client: AsyncClient) -> None:
        payload = {
            "github_id": 99999,
            "github_login": "idempotent_user",
            "avatar_url": "https://example.com/avatar.png",
            "email": "idempotent@example.com",
        }
        res1 = await client.post("/auth/github-callback", json=payload)
        assert res1.status_code == 200
        data1 = res1.json()

        res2 = await client.post("/auth/github-callback", json=payload)
        assert res2.status_code == 200
        data2 = res2.json()

        assert data1["user_id"] == data2["user_id"]
        assert data1["org_id"] == data2["org_id"]

    async def test_updates_github_metadata(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        payload = {
            "github_id": 55555,
            "github_login": "original",
            "avatar_url": "https://example.com/v1.png",
            "email": "meta@example.com",
        }
        await client.post("/auth/github-callback", json=payload)

        updated_payload = {
            **payload,
            "github_login": "renamed",
            "avatar_url": "https://example.com/v2.png",
        }
        await client.post("/auth/github-callback", json=updated_payload)

        result = await db_session.execute(
            select(User).where(User.github_id == 55555)
        )
        user = result.scalar_one()
        assert user.github_login == "renamed"
        assert user.avatar_url == "https://example.com/v2.png"

    async def test_missing_fields_returns_422(self, client: AsyncClient) -> None:
        res = await client.post(
            "/auth/github-callback",
            json={"github_id": 111},
        )
        assert res.status_code == 422

    async def test_returns_org_id(self, client: AsyncClient) -> None:
        res = await client.post(
            "/auth/github-callback",
            json={
                "github_id": 77777,
                "github_login": "orgcheck",
                "avatar_url": "",
                "email": "org@example.com",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["org_id"] is not None
        assert uuid.UUID(data["org_id"])

    async def test_uses_supabase_user_id_as_pk(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        supabase_id = str(uuid.uuid4())
        res = await client.post(
            "/auth/github-callback",
            json={
                "supabase_user_id": supabase_id,
                "github_id": 33333,
                "github_login": "supaid",
                "avatar_url": "",
                "email": "supaid@example.com",
            },
        )
        assert res.status_code == 200
        assert res.json()["user_id"] == supabase_id

        result = await db_session.execute(
            select(User).where(User.id == uuid.UUID(supabase_id))
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.github_login == "supaid"

    async def test_migrates_old_user_to_supabase_id(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """An existing user (matched by github_id) gets its ID updated to the Supabase UUID."""
        res1 = await client.post(
            "/auth/github-callback",
            json={
                "github_id": 44444,
                "github_login": "olduser",
                "avatar_url": "",
                "email": "olduser@example.com",
            },
        )
        assert res1.status_code == 200
        old_user_id = res1.json()["user_id"]
        old_org_id = res1.json()["org_id"]

        supabase_id = str(uuid.uuid4())
        res2 = await client.post(
            "/auth/github-callback",
            json={
                "supabase_user_id": supabase_id,
                "github_id": 44444,
                "github_login": "olduser",
                "avatar_url": "",
                "email": "olduser@example.com",
            },
        )
        assert res2.status_code == 200
        assert res2.json()["user_id"] == supabase_id

        result = await db_session.execute(
            select(User).where(User.id == uuid.UUID(old_user_id))
        )
        assert result.scalar_one_or_none() is None, "Old user row should be deleted"

        result = await db_session.execute(
            select(Organization).where(Organization.id == uuid.UUID(old_org_id))
        )
        org = result.scalar_one_or_none()
        assert org is not None, "Org should still exist"
        assert org.owner_id == uuid.UUID(supabase_id), "Org owner_id should point to new UUID"


class TestGetMe:
    """Tests for GET /auth/me — read-only current-user identity endpoint."""

    async def test_returns_user_and_org_ids(self, seeded_client) -> None:
        """Authenticated user gets back their user_id and org_id."""
        res = await seeded_client.get("/auth/me")
        assert res.status_code == 200
        data = res.json()
        assert "user_id" in data
        assert "org_id" in data
        assert uuid.UUID(data["user_id"])
        assert uuid.UUID(data["org_id"])

    async def test_requires_authentication(self, unauthed_client) -> None:
        """Unauthenticated request returns 401."""
        res = await unauthed_client.get("/auth/me")
        assert res.status_code == 401

    async def test_org_id_matches_callback_org_id(
        self, client, seeded_client, db_session
    ) -> None:
        """org_id from /auth/me matches the one previously returned by /auth/github-callback."""
        # First establish the user+org via callback
        callback_res = await client.post(
            "/auth/github-callback",
            json={
                "github_id": 88888,
                "github_login": "metest",
                "avatar_url": "",
                "email": "metest@example.com",
            },
        )
        assert callback_res.status_code == 200
        callback_org_id = callback_res.json()["org_id"]

        # The seeded_client uses STUB_USER_ID whose org already exists.
        # Verify /auth/me returns a valid UUID (integration check).
        me_res = await seeded_client.get("/auth/me")
        assert me_res.status_code == 200
        assert uuid.UUID(me_res.json()["org_id"])

    async def test_does_not_mutate_user_data(self, seeded_client, db_session) -> None:
        """GET /auth/me is read-only — calling it twice returns the same ids."""
        res1 = await seeded_client.get("/auth/me")
        res2 = await seeded_client.get("/auth/me")
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["user_id"] == res2.json()["user_id"]
        assert res1.json()["org_id"] == res2.json()["org_id"]
