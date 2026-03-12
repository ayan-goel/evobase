"""Unit tests for billing service layer."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.billing.service import (
    apply_tier_upgrade,
    get_or_create_subscription,
    get_period_spend,
    get_usage_pct,
)
from app.billing.token_pricing import TIER_API_BUDGETS
from app.db.models import Base, Organization, Repository, Run, Subscription, TokenUsageEvent, User

pytestmark = pytest.mark.asyncio

FIXED_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
FIXED_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
FIXED_REPO_ID = uuid.UUID("00000000-0000-0000-0000-000000000100")
FIXED_RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000200")


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
async def db_session(async_engine) -> AsyncSession:
    session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


async def _seed_user_and_org(db: AsyncSession) -> None:
    user = User(id=FIXED_USER_ID, email="test@example.com")
    db.add(user)
    await db.flush()
    org = Organization(id=FIXED_ORG_ID, name="Test Org", owner_id=FIXED_USER_ID)
    db.add(org)
    await db.flush()


async def _seed_subscription(db: AsyncSession, tier: str = "free") -> Subscription:
    now = datetime.now(timezone.utc)
    sub = Subscription(
        org_id=FIXED_ORG_ID,
        tier=tier,
        status="active",
        current_period_start=now - timedelta(days=5),
        current_period_end=now + timedelta(days=25),
        included_api_budget_microdollars=TIER_API_BUDGETS[tier],
        overage_allowed=(tier != "free"),
    )
    db.add(sub)
    await db.flush()
    return sub


async def _seed_run(db: AsyncSession) -> None:
    repo = Repository(
        id=FIXED_REPO_ID,
        org_id=FIXED_ORG_ID,
        default_branch="main",
    )
    db.add(repo)
    await db.flush()
    run = Run(id=FIXED_RUN_ID, repo_id=FIXED_REPO_ID, status="completed")
    db.add(run)
    await db.flush()


async def _seed_usage_events(
    db: AsyncSession,
    api_costs: list[int],
    *,
    within_period: bool = True,
) -> None:
    from sqlalchemy import select

    result = await db.execute(select(Subscription).where(Subscription.org_id == FIXED_ORG_ID))
    sub = result.scalar_one()
    created = sub.current_period_start + timedelta(hours=1) if within_period else sub.current_period_start - timedelta(hours=1)

    for cost in api_costs:
        event = TokenUsageEvent(
            org_id=FIXED_ORG_ID,
            run_id=FIXED_RUN_ID,
            call_type="patch_gen",
            provider="anthropic",
            model="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=50,
            api_cost_microdollars=cost,
            billed_microdollars=round(cost * 1.5),
            rate_type="included",
        )
        event.created_at = created
        db.add(event)
    await db.flush()


class TestGetOrCreateSubscription:
    async def test_returns_existing_subscription(self, db_session):
        await _seed_user_and_org(db_session)
        existing = await _seed_subscription(db_session, "hobby")
        await db_session.commit()

        result = await get_or_create_subscription(db_session, FIXED_ORG_ID)
        assert result.id == existing.id
        assert result.tier == "hobby"

    async def test_auto_creates_free_tier_when_missing(self, db_session):
        await _seed_user_and_org(db_session)
        await db_session.commit()

        result = await get_or_create_subscription(db_session, FIXED_ORG_ID)
        assert result.tier == "free"
        assert result.status == "active"
        assert result.overage_allowed is False
        assert result.included_api_budget_microdollars == TIER_API_BUDGETS["free"]

    async def test_auto_created_has_valid_period_dates(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await get_or_create_subscription(db_session, FIXED_ORG_ID)
        assert sub.current_period_end > sub.current_period_start
        assert 29 <= (sub.current_period_end - sub.current_period_start).days <= 31

    async def test_idempotent_on_second_call(self, db_session):
        await _seed_user_and_org(db_session)
        sub1 = await get_or_create_subscription(db_session, FIXED_ORG_ID)
        await db_session.commit()
        sub2 = await get_or_create_subscription(db_session, FIXED_ORG_ID)
        assert sub1.id == sub2.id


class TestGetPeriodSpend:
    async def test_zero_when_no_events(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await _seed_subscription(db_session)
        await _seed_run(db_session)
        await db_session.commit()
        spent = await get_period_spend(db_session, FIXED_ORG_ID, sub.current_period_start)
        assert spent == 0

    async def test_sums_events_in_period(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await _seed_subscription(db_session)
        await _seed_run(db_session)
        await _seed_usage_events(db_session, [1000, 2000, 3000], within_period=True)
        await db_session.commit()
        spent = await get_period_spend(db_session, FIXED_ORG_ID, sub.current_period_start)
        assert spent == 6000


class TestGetUsagePct:
    async def test_zero_percent_with_no_spend(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await _seed_subscription(db_session, "hobby")
        await _seed_run(db_session)
        await db_session.commit()
        pct = await get_usage_pct(db_session, sub)
        assert pct == 0.0

    async def test_fifty_percent_usage(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await _seed_subscription(db_session, "hobby")
        await _seed_run(db_session)
        await _seed_usage_events(db_session, [sub.included_api_budget_microdollars // 2], within_period=True)
        await db_session.commit()
        pct = await get_usage_pct(db_session, sub)
        assert pct == pytest.approx(50.0, abs=0.5)

    async def test_over_100_percent_when_in_overage(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await _seed_subscription(db_session, "hobby")
        await _seed_run(db_session)
        await _seed_usage_events(db_session, [sub.included_api_budget_microdollars * 2], within_period=True)
        await db_session.commit()
        pct = await get_usage_pct(db_session, sub)
        assert pct > 100.0

    async def test_100_percent_when_budget_is_zero(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await _seed_subscription(db_session)
        sub.included_api_budget_microdollars = 0
        await db_session.flush()
        await db_session.commit()
        pct = await get_usage_pct(db_session, sub)
        assert pct == 100.0


class TestApplyTierUpgrade:
    async def test_upgrade_free_to_hobby(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await _seed_subscription(db_session, "free")
        await db_session.commit()
        await apply_tier_upgrade(db_session, sub, "hobby")
        assert sub.tier == "hobby"
        assert sub.overage_allowed is True
        assert sub.included_api_budget_microdollars == TIER_API_BUDGETS["hobby"]

    async def test_upgrade_sets_new_period_dates(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await _seed_subscription(db_session, "free")
        old_start = sub.current_period_start
        await db_session.commit()
        await apply_tier_upgrade(db_session, sub, "premium")
        assert sub.current_period_start >= old_start

    async def test_upgrade_to_pro(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await _seed_subscription(db_session, "hobby")
        await db_session.commit()
        await apply_tier_upgrade(db_session, sub, "pro")
        assert sub.tier == "pro"
        assert sub.included_api_budget_microdollars == TIER_API_BUDGETS["pro"]

    async def test_invalid_tier_raises_value_error(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await _seed_subscription(db_session)
        await db_session.commit()
        with pytest.raises(ValueError, match="Invalid tier"):
            await apply_tier_upgrade(db_session, sub, "ultra-premium-gold")

    async def test_stripe_subscription_id_stored(self, db_session):
        await _seed_user_and_org(db_session)
        sub = await _seed_subscription(db_session)
        await db_session.commit()
        await apply_tier_upgrade(db_session, sub, "hobby", stripe_subscription_id="sub_abc123")
        assert sub.stripe_subscription_id == "sub_abc123"
