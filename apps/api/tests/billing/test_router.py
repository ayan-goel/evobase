"""Focused integration tests for the /billing router."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import AsyncGenerator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.dependencies import get_current_user
from app.billing.router import router as billing_router
from app.billing.token_pricing import TIER_API_BUDGETS
from app.core.config import Settings, get_settings
from app.db.models import Base, Organization, Repository, Run, Subscription, TokenUsageEvent, User
from app.db.session import get_db

pytestmark = pytest.mark.asyncio

STUB_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
STUB_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
STUB_REPO_ID = uuid.UUID("00000000-0000-0000-0000-000000000100")
STUB_RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000200")


@pytest.fixture
def override_settings() -> Settings:
    return Settings(
        supabase_jwt_secret="test-secret",
        database_url="sqlite+aiosqlite:///:memory:",
        sentry_dsn="",
        debug=False,
        stripe_publishable_key="pk_test_abc",
        stripe_secret_key="sk_test_abc",
    )


@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def seeded_db(async_engine) -> AsyncSession:
    session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        user = User(id=STUB_USER_ID, email="dev@evobase.local")
        session.add(user)
        await session.flush()

        org = Organization(id=STUB_ORG_ID, name="Dev Organization", owner_id=user.id)
        session.add(org)
        await session.flush()

        repo = Repository(
            id=STUB_REPO_ID,
            org_id=org.id,
            github_repo_id=123456789,
            default_branch="main",
            package_manager="npm",
            install_cmd="npm install",
            build_cmd="npm run build",
            test_cmd="npm test",
        )
        session.add(repo)
        await session.commit()
        yield session


@pytest.fixture
def authed_app(async_engine, override_settings):
    app = FastAPI()
    app.include_router(billing_router)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        session_factory = async_sessionmaker(
            async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_current_user() -> uuid.UUID:
        return STUB_USER_ID

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_settings] = lambda: override_settings
    return app


@pytest.fixture
def unauthed_app(async_engine, override_settings):
    app = FastAPI()
    app.include_router(billing_router)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        session_factory = async_sessionmaker(
            async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: override_settings
    return app


@pytest.fixture
async def authed_client(authed_app, seeded_db) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=authed_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def unauthed_client(unauthed_app, seeded_db) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=unauthed_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _seed_free_subscription(db_session: AsyncSession) -> Subscription:
    now = datetime.now(timezone.utc)
    sub = Subscription(
        org_id=STUB_ORG_ID,
        tier="free",
        status="active",
        current_period_start=now - timedelta(days=5),
        current_period_end=now + timedelta(days=25),
        included_api_budget_microdollars=TIER_API_BUDGETS["free"],
        overage_allowed=False,
    )
    db_session.add(sub)
    await db_session.flush()
    return sub


async def _seed_hobby_subscription(db_session: AsyncSession) -> Subscription:
    now = datetime.now(timezone.utc)
    sub = Subscription(
        org_id=STUB_ORG_ID,
        tier="hobby",
        status="active",
        current_period_start=now - timedelta(days=5),
        current_period_end=now + timedelta(days=25),
        included_api_budget_microdollars=TIER_API_BUDGETS["hobby"],
        overage_allowed=True,
        stripe_customer_id="cus_test",
        stripe_subscription_id="sub_test",
    )
    db_session.add(sub)
    await db_session.flush()
    return sub


async def _seed_run_with_events(db_session: AsyncSession, api_cost: int = 50_000) -> None:
    run = Run(id=STUB_RUN_ID, repo_id=STUB_REPO_ID, status="completed")
    db_session.add(run)
    await db_session.flush()

    event = TokenUsageEvent(
        org_id=STUB_ORG_ID,
        run_id=STUB_RUN_ID,
        call_type="patch_gen",
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=1000,
        output_tokens=500,
        api_cost_microdollars=api_cost,
        billed_microdollars=round(api_cost * 1.5),
        rate_type="included",
    )
    db_session.add(event)
    await db_session.flush()


class TestBillingConfig:
    async def test_returns_publishable_key(self, authed_client):
        with patch("app.billing.router.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(
                supabase_jwt_secret="test-secret",
                database_url="sqlite+aiosqlite:///:memory:",
                sentry_dsn="",
                debug=False,
                stripe_publishable_key="pk_test_abc",
            )
            response = await authed_client.get("/billing/config")
        assert response.status_code == 200
        assert response.json() == {"publishable_key": "pk_test_abc"}


class TestGetSubscription:
    async def test_returns_subscription_for_seeded_org(self, authed_client, seeded_db):
        await _seed_free_subscription(seeded_db)
        await seeded_db.commit()

        response = await authed_client.get("/billing/subscription")
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "free"
        assert data["status"] == "active"
        assert data["usage_pct"] == 0.0
        assert data["overage_active"] is False

    async def test_auto_creates_subscription_if_missing(self, authed_client):
        response = await authed_client.get("/billing/subscription")
        assert response.status_code == 200
        assert response.json()["tier"] == "free"

    async def test_usage_pct_reflects_events(self, authed_client, seeded_db):
        sub = await _seed_free_subscription(seeded_db)
        await _seed_run_with_events(seeded_db, api_cost=sub.included_api_budget_microdollars // 2)
        await seeded_db.commit()

        response = await authed_client.get("/billing/subscription")
        assert response.status_code == 200
        assert response.json()["usage_pct"] == pytest.approx(50.0, abs=1.0)

    async def test_unauthenticated_returns_401(self, unauthed_client):
        response = await unauthed_client.get("/billing/subscription")
        assert response.status_code == 401


class TestGetUsage:
    async def test_empty_usage_list(self, authed_client):
        response = await authed_client.get("/billing/usage")
        assert response.status_code == 200
        assert response.json()["runs"] == []

    async def test_usage_includes_run_row(self, authed_client, seeded_db):
        await _seed_free_subscription(seeded_db)
        await _seed_run_with_events(seeded_db, api_cost=100_000)
        await seeded_db.commit()

        response = await authed_client.get("/billing/usage")
        assert response.status_code == 200
        row = response.json()["runs"][0]
        assert row["run_id"] == str(STUB_RUN_ID)
        assert row["api_cost_microdollars"] == 100_000

    async def test_unauthenticated_returns_401(self, unauthed_client):
        response = await unauthed_client.get("/billing/usage")
        assert response.status_code == 401


class TestUpdateSpendLimit:
    async def test_sets_spend_limit(self, authed_client, seeded_db):
        await _seed_hobby_subscription(seeded_db)
        await seeded_db.commit()

        response = await authed_client.patch(
            "/billing/spend-limit",
            json={"monthly_spend_limit_microdollars": 50_000_000},
        )
        assert response.status_code == 200
        assert response.json()["monthly_spend_limit_microdollars"] == 50_000_000

    async def test_clears_spend_limit_with_null(self, authed_client, seeded_db):
        sub = await _seed_hobby_subscription(seeded_db)
        sub.monthly_spend_limit_microdollars = 50_000_000
        await seeded_db.commit()

        response = await authed_client.patch(
            "/billing/spend-limit",
            json={"monthly_spend_limit_microdollars": None},
        )
        assert response.status_code == 200
        assert response.json()["monthly_spend_limit_microdollars"] is None

    async def test_negative_spend_limit_rejected(self, authed_client, seeded_db):
        await _seed_hobby_subscription(seeded_db)
        await seeded_db.commit()

        response = await authed_client.patch(
            "/billing/spend-limit",
            json={"monthly_spend_limit_microdollars": -1},
        )
        assert response.status_code == 422

    async def test_free_tier_cannot_set_spend_limit(self, authed_client, seeded_db):
        await _seed_free_subscription(seeded_db)
        await seeded_db.commit()

        response = await authed_client.patch(
            "/billing/spend-limit",
            json={"monthly_spend_limit_microdollars": 1_000_000},
        )
        assert response.status_code == 400

    async def test_unauthenticated_returns_401(self, unauthed_client):
        response = await unauthed_client.patch(
            "/billing/spend-limit",
            json={"monthly_spend_limit_microdollars": 50_000_000},
        )
        assert response.status_code == 401


class TestCancelSubscription:
    async def test_cancel_paid_subscription(self, authed_client, seeded_db):
        await _seed_hobby_subscription(seeded_db)
        await seeded_db.commit()

        with patch("app.billing.router.get_settings") as mock_get_settings, patch(
            "app.billing.stripe_client.cancel_subscription"
        ) as mock_cancel:
            mock_get_settings.return_value = Settings(
                supabase_jwt_secret="test-secret",
                database_url="sqlite+aiosqlite:///:memory:",
                sentry_dsn="",
                debug=False,
                stripe_secret_key="sk_test_abc",
            )
            response = await authed_client.post("/billing/subscription/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "canceled"
        assert data["tier"] == "hobby"
        mock_cancel.assert_called_once_with("sub_test")

    async def test_cancel_free_subscription_is_allowed(self, authed_client, seeded_db):
        await _seed_free_subscription(seeded_db)
        await seeded_db.commit()

        response = await authed_client.post("/billing/subscription/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "canceled"


class TestUpgradeSubscription:
    async def test_syncs_local_tier_when_stripe_is_already_on_requested_plan(self, authed_client, seeded_db):
        sub = await _seed_free_subscription(seeded_db)
        sub.stripe_customer_id = "cus_test"
        sub.stripe_subscription_id = "sub_test"
        await seeded_db.commit()

        stripe_sub = SimpleNamespace(
            items=SimpleNamespace(
                data=[
                    SimpleNamespace(
                        price=SimpleNamespace(id="price_1TALotBTGYNBUsYj2nFWe1UJ")
                    )
                ]
            )
        )

        with patch("app.billing.router.get_settings") as mock_get_settings, patch(
            "app.billing.stripe_client.retrieve_subscription",
            return_value=stripe_sub,
        ) as mock_retrieve, patch(
            "app.billing.stripe_client.update_subscription_tier"
        ) as mock_update:
            mock_get_settings.return_value = Settings(
                supabase_jwt_secret="test-secret",
                database_url="sqlite+aiosqlite:///:memory:",
                sentry_dsn="",
                debug=False,
                stripe_secret_key="sk_test_abc",
            )
            response = await authed_client.post(
                "/billing/subscription/upgrade",
                json={"tier": "hobby"},
            )

        assert response.status_code == 200
        assert response.json() == {"tier": "hobby", "status": "active"}
        mock_retrieve.assert_called_once_with("sub_test")
        mock_update.assert_not_called()

        subscription_response = await authed_client.get("/billing/subscription")
        assert subscription_response.status_code == 200
        assert subscription_response.json()["tier"] == "hobby"
