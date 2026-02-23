"""Integration tests for GET/PUT /repos/{repo_id}/settings.

Tests cover:
- GET: auto-creates defaults, returns correct schema
- GET: 404 for unknown repo
- PUT: partial update (individual fields)
- PUT: unpause resets failure counters
- PUT: 404 for unknown repo
- PUT: invalid field values (e.g. budget <= 0)
- Auth: 401 when no auth header is provided
- Auth: 404 when repo belongs to a different user
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, Repository, Settings, User
from tests.conftest import STUB_REPO_ID, STUB_USER_ID, _make_jwt


# ---------------------------------------------------------------------------
# GET /repos/{repo_id}/settings
# ---------------------------------------------------------------------------


class TestGetSettings:
    async def test_returns_defaults_when_no_row(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.get(f"/repos/{STUB_REPO_ID}/settings")
        assert res.status_code == 200
        data = res.json()
        assert data["repo_id"] == str(STUB_REPO_ID)
        assert data["compute_budget_minutes"] == 60
        assert data["max_proposals_per_run"] == 10
        assert data["max_candidates_per_run"] == 20
        assert data["paused"] is False
        assert data["consecutive_setup_failures"] == 0
        assert data["consecutive_flaky_runs"] == 0
        assert data["execution_mode"] == "adaptive"
        assert data["max_strategy_attempts"] == 2

    async def test_creates_settings_row_on_first_get(
        self, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        await seeded_client.get(f"/repos/{STUB_REPO_ID}/settings")
        result = await seeded_db.execute(
            select(Settings).where(Settings.repo_id == STUB_REPO_ID)
        )
        assert result.scalar_one_or_none() is not None

    async def test_returns_existing_settings(
        self, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        seeded_db.add(
            Settings(
                repo_id=STUB_REPO_ID,
                compute_budget_minutes=120,
                max_proposals_per_run=3,
            )
        )
        await seeded_db.commit()

        res = await seeded_client.get(f"/repos/{STUB_REPO_ID}/settings")
        assert res.status_code == 200
        data = res.json()
        assert data["compute_budget_minutes"] == 120
        assert data["max_proposals_per_run"] == 3

    async def test_returns_404_for_unknown_repo(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.get(f"/repos/{uuid.uuid4()}/settings")
        assert res.status_code == 404

    async def test_response_schema_has_all_fields(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.get(f"/repos/{STUB_REPO_ID}/settings")
        data = res.json()
        expected_keys = {
            "repo_id", "compute_budget_minutes", "max_prs_per_day",
            "max_proposals_per_run", "max_candidates_per_run", "schedule", "paused",
            "consecutive_setup_failures", "consecutive_flaky_runs", "last_run_at",
            "execution_mode", "max_strategy_attempts",
        }
        assert expected_keys.issubset(data.keys())


# ---------------------------------------------------------------------------
# PUT /repos/{repo_id}/settings
# ---------------------------------------------------------------------------


class TestUpdateSettings:
    async def test_updates_budget_minutes(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"compute_budget_minutes": 30},
        )
        assert res.status_code == 200
        assert res.json()["compute_budget_minutes"] == 30

    async def test_updates_max_proposals(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"max_proposals_per_run": 3},
        )
        assert res.status_code == 200
        assert res.json()["max_proposals_per_run"] == 3

    async def test_updates_max_candidates(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"max_candidates_per_run": 5},
        )
        assert res.status_code == 200
        assert res.json()["max_candidates_per_run"] == 5

    async def test_updates_max_prs_per_day(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"max_prs_per_day": 10},
        )
        assert res.status_code == 200
        assert res.json()["max_prs_per_day"] == 10

    async def test_max_prs_per_day_defaults_to_five(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.get(f"/repos/{STUB_REPO_ID}/settings")
        assert res.status_code == 200
        assert res.json()["max_prs_per_day"] == 5

    async def test_updates_schedule(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"schedule": "0 6 * * *"},
        )
        assert res.status_code == 200
        assert res.json()["schedule"] == "0 6 * * *"

    async def test_updates_paused_to_true(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"paused": True},
        )
        assert res.status_code == 200
        assert res.json()["paused"] is True

    async def test_unpause_resets_failure_counters(
        self, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        seeded_db.add(
            Settings(
                repo_id=STUB_REPO_ID,
                paused=True,
                consecutive_setup_failures=3,
                consecutive_flaky_runs=5,
            )
        )
        await seeded_db.commit()

        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"paused": False},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["paused"] is False
        assert data["consecutive_setup_failures"] == 0
        assert data["consecutive_flaky_runs"] == 0

    async def test_partial_update_preserves_other_fields(
        self, seeded_client: AsyncClient
    ) -> None:
        # First set known values
        await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"compute_budget_minutes": 90, "max_proposals_per_run": 7},
        )
        # Then update only one field
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"compute_budget_minutes": 45},
        )
        data = res.json()
        assert data["compute_budget_minutes"] == 45
        assert data["max_proposals_per_run"] == 7  # unchanged

    async def test_returns_404_for_unknown_repo(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{uuid.uuid4()}/settings",
            json={"compute_budget_minutes": 30},
        )
        assert res.status_code == 404

    async def test_empty_body_is_valid_noop(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={},
        )
        assert res.status_code == 200

    async def test_rejects_zero_budget_minutes(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"compute_budget_minutes": 0},
        )
        assert res.status_code == 422

    async def test_updates_llm_provider(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"llm_provider": "openai", "llm_model": "gpt-4o"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["llm_provider"] == "openai"
        assert data["llm_model"] == "gpt-4o"

    async def test_llm_provider_defaults_to_anthropic(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.get(f"/repos/{STUB_REPO_ID}/settings")
        data = res.json()
        assert data["llm_provider"] == "anthropic"
        assert data["llm_model"] == "claude-sonnet-4-5"

    async def test_updates_llm_model_independently(self, seeded_client: AsyncClient) -> None:
        await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"llm_provider": "anthropic", "llm_model": "claude-haiku-3-5"},
        )
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"llm_model": "claude-sonnet-4-5"},
        )
        data = res.json()
        assert data["llm_model"] == "claude-sonnet-4-5"
        assert data["llm_provider"] == "anthropic"  # unchanged

    async def test_updates_execution_mode_and_attempts(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"execution_mode": "strict", "max_strategy_attempts": 1},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["execution_mode"] == "strict"
        assert data["max_strategy_attempts"] == 1

    async def test_rejects_invalid_execution_mode(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"execution_mode": "experimental"},
        )
        assert res.status_code == 422

    async def test_rejects_invalid_max_strategy_attempts(self, seeded_client: AsyncClient) -> None:
        res = await seeded_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"max_strategy_attempts": 5},
        )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


class TestSettingsAuth:
    async def test_get_settings_without_auth_returns_401(
        self, unauthed_client: AsyncClient
    ) -> None:
        res = await unauthed_client.get(f"/repos/{STUB_REPO_ID}/settings")
        assert res.status_code == 401

    async def test_put_settings_without_auth_returns_401(
        self, unauthed_client: AsyncClient
    ) -> None:
        res = await unauthed_client.put(
            f"/repos/{STUB_REPO_ID}/settings",
            json={"compute_budget_minutes": 30},
        )
        assert res.status_code == 401

    async def test_get_settings_with_auth_succeeds(
        self, seeded_client: AsyncClient
    ) -> None:
        res = await seeded_client.get(f"/repos/{STUB_REPO_ID}/settings")
        assert res.status_code == 200

    async def test_put_settings_wrong_user_returns_404(
        self, app, seeded_db: AsyncSession
    ) -> None:
        """A valid JWT for a different user should get 404 (not their repo)."""
        from httpx import ASGITransport, AsyncClient as HC

        other_user_id = uuid.uuid4()
        other_user = User(id=other_user_id, email="other@example.com")
        seeded_db.add(other_user)
        await seeded_db.commit()

        token = _make_jwt(sub=other_user_id)
        transport = ASGITransport(app=app)
        async with HC(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as ac:
            res = await ac.put(
                f"/repos/{STUB_REPO_ID}/settings",
                json={"compute_budget_minutes": 30},
            )
            assert res.status_code == 404
