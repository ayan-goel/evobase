"""Tests for JWT-based authentication dependency."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ec import (
    SECP256R1,
    generate_private_key,
)
from cryptography.hazmat.backends import default_backend
from httpx import AsyncClient
from jose import jwt as jose_jwt
from jose.backends import ECKey

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

    async def test_es256_jwt_is_accepted(self, app, seeded_db) -> None:
        """ES256-signed JWTs (Supabase ECC P-256 key) are verified via JWKS."""
        from datetime import datetime, timezone, timedelta
        from httpx import ASGITransport, AsyncClient as HC

        # Generate a throwaway EC P-256 key pair
        private_key = generate_private_key(SECP256R1(), default_backend())
        ec_key = ECKey(private_key, algorithm="ES256")
        public_jwk = ec_key.public_key().to_dict()
        public_jwk["kid"] = "test-ec-kid"

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(STUB_USER_ID),
            "aud": "authenticated",
            "email": "dev@coreloop.local",
            "exp": now + timedelta(hours=1),
            "iat": now,
        }
        token = jose_jwt.encode(
            payload,
            ec_key.to_dict(),
            algorithm="ES256",
            headers={"kid": "test-ec-kid"},
        )

        fake_jwks = {"keys": [public_jwk]}
        mock_fetch = AsyncMock(return_value=fake_jwks)

        import app.auth.dependencies as deps
        original_cache = deps._jwks_cache
        deps._jwks_cache = None

        transport = ASGITransport(app=app)
        with patch("app.auth.dependencies._fetch_jwks", mock_fetch):
            async with HC(
                transport=transport,
                base_url="http://test",
                headers={"Authorization": f"Bearer {token}"},
            ) as ac:
                res = await ac.get("/repos")
                assert res.status_code == 200

        deps._jwks_cache = original_cache

    async def test_unsupported_alg_raises_401(self, app, seeded_db) -> None:
        """JWTs signed with an unknown algorithm are rejected."""
        from httpx import ASGITransport, AsyncClient as HC
        from datetime import datetime, timezone, timedelta

        # RS256 is not in our allowed list
        payload = {
            "sub": str(STUB_USER_ID),
            "aud": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        # Craft a token with a fake RS256 header (will fail header parse / alg check)
        token = jose_jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        # Manually tamper the header to claim RS256
        import base64, json
        header_b64 = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()
        parts = token.split(".")
        bad_token = f"{header_b64}.{parts[1]}.{parts[2]}"

        transport = ASGITransport(app=app)
        async with HC(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {bad_token}"},
        ) as ac:
            res = await ac.get("/repos")
            assert res.status_code == 401
