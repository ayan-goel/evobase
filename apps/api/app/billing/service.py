"""Billing service layer.

Encapsulates all billing business logic: subscription lookups, usage
aggregation, and Stripe coordination.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.token_pricing import TIER_API_BUDGETS, TIER_OVERAGE_ALLOWED
from app.db.models import Subscription, TokenUsageEvent

logger = logging.getLogger(__name__)

# Tier display order for validation
VALID_TIERS = ("free", "hobby", "premium", "pro")


async def get_or_create_subscription(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> Subscription:
    """Load the subscription for this org, auto-creating a free row if absent."""
    result = await db.execute(select(Subscription).where(Subscription.org_id == org_id))
    sub = result.scalar_one_or_none()
    if sub:
        return sub

    now = datetime.now(timezone.utc)
    sub = Subscription(
        org_id=org_id,
        tier="free",
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        included_api_budget_microdollars=TIER_API_BUDGETS["free"],
        overage_allowed=TIER_OVERAGE_ALLOWED["free"],
    )
    db.add(sub)
    await db.flush()
    logger.info("Auto-created free-tier subscription for org %s", org_id)
    return sub


async def get_period_spend(
    db: AsyncSession,
    org_id: uuid.UUID,
    period_start: datetime,
) -> int:
    """Return total api_cost_microdollars for this org in the current period."""
    result = await db.scalar(
        select(func.coalesce(func.sum(TokenUsageEvent.api_cost_microdollars), 0))
        .where(TokenUsageEvent.org_id == org_id)
        .where(TokenUsageEvent.created_at >= period_start)
    )
    return int(result or 0)


async def get_usage_pct(db: AsyncSession, sub: Subscription) -> float:
    """Return usage as a percentage (0–100+) of the included API budget."""
    spent = await get_period_spend(db, sub.org_id, sub.current_period_start)
    budget = sub.included_api_budget_microdollars
    if budget <= 0:
        return 100.0
    return round((spent / budget) * 100, 1)


async def get_per_run_usage(
    db: AsyncSession,
    org_id: uuid.UUID,
    period_start: datetime,
) -> list[dict]:
    """Return per-run cost breakdown for the current period."""
    rows = await db.execute(
        select(
            TokenUsageEvent.run_id,
            func.min(TokenUsageEvent.created_at).label("created_at"),
            func.sum(TokenUsageEvent.api_cost_microdollars).label("api_cost"),
            func.sum(TokenUsageEvent.billed_microdollars).label("billed"),
            func.count(TokenUsageEvent.id).label("call_count"),
        )
        .where(TokenUsageEvent.org_id == org_id)
        .where(TokenUsageEvent.created_at >= period_start)
        .group_by(TokenUsageEvent.run_id)
        .order_by(func.min(TokenUsageEvent.created_at).desc())
    )
    return [
        {
            "run_id": str(row.run_id),
            "created_at": row.created_at,
            "api_cost_microdollars": int(row.api_cost),
            "billed_microdollars": int(row.billed),
            "call_count": int(row.call_count),
        }
        for row in rows
    ]


def _budget_for_tier(tier: str) -> int:
    return TIER_API_BUDGETS.get(tier, TIER_API_BUDGETS["free"])


def _overage_for_tier(tier: str) -> bool:
    return TIER_OVERAGE_ALLOWED.get(tier, False)


async def apply_tier_upgrade(
    db: AsyncSession,
    sub: Subscription,
    tier: str,
    stripe_subscription_id: Optional[str] = None,
) -> Subscription:
    """Update the subscription tier and re-set the included budget."""
    if tier not in VALID_TIERS:
        raise ValueError(f"Invalid tier: {tier}")

    now = datetime.now(timezone.utc)
    sub.tier = tier
    sub.status = "active"
    sub.included_api_budget_microdollars = _budget_for_tier(tier)
    sub.overage_allowed = _overage_for_tier(tier)
    if stripe_subscription_id:
        sub.stripe_subscription_id = stripe_subscription_id
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=30)
    sub.updated_at = now
    await db.flush()
    return sub
