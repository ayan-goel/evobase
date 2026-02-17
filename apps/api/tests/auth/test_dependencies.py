"""Tests for the auth stub dependency."""

import uuid

import pytest

from app.auth.dependencies import STUB_USER_ID, get_current_user


class TestAuthStub:
    async def test_stub_returns_deterministic_user_id(self):
        user_id = await get_current_user()
        assert user_id == STUB_USER_ID

    async def test_stub_user_id_is_valid_uuid(self):
        user_id = await get_current_user()
        assert isinstance(user_id, uuid.UUID)

    async def test_stub_ignores_authorization_header(self):
        """The stub accepts any authorization value."""
        user_id = await get_current_user(authorization="Bearer real-token")
        assert user_id == STUB_USER_ID
