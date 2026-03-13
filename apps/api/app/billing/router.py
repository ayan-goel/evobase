"""Billing endpoints.

Routes:
  GET  /billing/config                   — return Stripe publishable key
  GET  /billing/subscription             — current tier, period, usage %
  POST /billing/checkout                 — create Stripe Customer + Subscription
  POST /billing/subscription/upgrade     — change tier via Stripe proration
  POST /billing/subscription/cancel      — cancel at period end
  PATCH /billing/spend-limit             — set/clear monthly overage cap
  GET  /billing/usage                    — per-run cost breakdown (current period)
  POST /billing/webhook                  — Stripe webhook (signature-verified)
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.billing import service as billing_service
from app.billing.schemas import (
    BillingConfigResponse,
    CheckoutRequest,
    CheckoutResponse,
    SpendLimitRequest,
    SubscriptionResponse,
    UpgradeRequest,
    UsageResponse,
    UsageRunRow,
)
from app.core.config import get_settings
from app.db.models import Organization, Subscription
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


async def _get_org_id(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> uuid.UUID:
    """Resolve the org_id for the current user. Raises 404 if not found."""
    result = await db.execute(
        select(Organization.id).where(Organization.owner_id == user_id)
    )
    org_id = result.scalar_one_or_none()
    if not org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org_id


@router.get("/config", response_model=BillingConfigResponse)
async def get_billing_config() -> BillingConfigResponse:
    """Return Stripe publishable key for the frontend to initialise Stripe.js."""
    settings = get_settings()
    return BillingConfigResponse(publishable_key=settings.stripe_publishable_key)


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> SubscriptionResponse:
    """Return current subscription tier, period dates, and usage percentage."""
    org_id = await _get_org_id(db, user_id)
    sub = await billing_service.get_or_create_subscription(db, org_id)
    await db.commit()

    usage_pct = await billing_service.get_usage_pct(db, sub)
    spent = await billing_service.get_period_spend(db, org_id, sub.current_period_start)
    overage_active = spent > sub.included_api_budget_microdollars

    return SubscriptionResponse(
        tier=sub.tier,
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        usage_pct=usage_pct,
        overage_active=overage_active,
        monthly_spend_limit_microdollars=sub.monthly_spend_limit_microdollars,
        stripe_customer_id=sub.stripe_customer_id,
        stripe_subscription_id=sub.stripe_subscription_id,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> CheckoutResponse:
    """Create a Stripe Customer + Subscription and return a PaymentIntent client_secret.

    The frontend uses the client_secret with Stripe.js <PaymentElement> to
    collect payment details without the user leaving the page.
    """
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing not configured",
        )

    org_id = await _get_org_id(db, user_id)
    sub = await billing_service.get_or_create_subscription(db, org_id)

    # Resolve user email for Stripe Customer creation
    from app.db.models import User
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    email = user.email if user else ""

    from app.billing import stripe_client
    stripe_client.configure(settings.stripe_secret_key)

    # Reuse existing Stripe Customer if available
    if not sub.stripe_customer_id:
        customer_id = stripe_client.create_customer(
            email=email,
            metadata={"org_id": str(org_id)},
        )
        sub.stripe_customer_id = customer_id
        await db.flush()
    else:
        customer_id = sub.stripe_customer_id

    stripe_sub = stripe_client.create_subscription(customer_id, body.tier)
    client_secret = stripe_client.get_client_secret_from_subscription(stripe_sub)
    if not client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not obtain payment intent client secret from Stripe",
        )

    sub.stripe_subscription_id = stripe_sub["id"]
    await db.commit()

    return CheckoutResponse(
        client_secret=client_secret,
        publishable_key=settings.stripe_publishable_key,
    )


@router.post("/subscription/upgrade")
async def upgrade_subscription(
    body: UpgradeRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> dict:
    """Change the subscription tier via Stripe proration."""
    settings = get_settings()
    org_id = await _get_org_id(db, user_id)
    sub = await billing_service.get_or_create_subscription(db, org_id)

    if settings.stripe_secret_key and sub.stripe_subscription_id:
        from app.billing import stripe_client
        stripe_client.configure(settings.stripe_secret_key)
        stripe_client.update_subscription_tier(sub.stripe_subscription_id, body.tier)

    await billing_service.apply_tier_upgrade(db, sub, body.tier)
    await db.commit()

    return {"tier": sub.tier, "status": sub.status}


@router.post("/subscription/cancel")
async def cancel_subscription(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> dict:
    """Cancel the subscription at the end of the current billing period."""
    settings = get_settings()
    org_id = await _get_org_id(db, user_id)
    sub = await billing_service.get_or_create_subscription(db, org_id)

    if settings.stripe_secret_key and sub.stripe_subscription_id:
        from app.billing import stripe_client
        stripe_client.configure(settings.stripe_secret_key)
        stripe_client.cancel_subscription(sub.stripe_subscription_id)

    sub.status = "canceled"
    sub.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "canceled", "tier": sub.tier}


@router.patch("/spend-limit")
async def update_spend_limit(
    body: SpendLimitRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> dict:
    """Set or clear the monthly overage spend cap."""
    org_id = await _get_org_id(db, user_id)
    sub = await billing_service.get_or_create_subscription(db, org_id)

    if sub.tier == "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free plan does not support overage. Upgrade to set a spend limit.",
        )

    sub.monthly_spend_limit_microdollars = body.monthly_spend_limit_microdollars
    sub.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "monthly_spend_limit_microdollars": sub.monthly_spend_limit_microdollars,
    }


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> UsageResponse:
    """Return per-run cost breakdown for the current billing period."""
    org_id = await _get_org_id(db, user_id)
    sub = await billing_service.get_or_create_subscription(db, org_id)
    await db.commit()

    run_rows = await billing_service.get_per_run_usage(db, org_id, sub.current_period_start)
    total_api = sum(r["api_cost_microdollars"] for r in run_rows)
    total_billed = sum(r["billed_microdollars"] for r in run_rows)
    budget = sub.included_api_budget_microdollars
    usage_pct = round((total_api / budget) * 100, 1) if budget > 0 else 100.0

    return UsageResponse(
        period_start=sub.current_period_start,
        period_end=sub.current_period_end,
        total_api_cost_microdollars=total_api,
        total_billed_microdollars=total_billed,
        included_api_budget_microdollars=budget,
        usage_pct=usage_pct,
        runs=[UsageRunRow(**r) for r in run_rows],
    )


@router.post("/webhook")
async def stripe_webhook(request: Request) -> dict:
    """Handle Stripe webhook events (signature-verified).

    Events handled:
      - customer.subscription.updated  → sync tier, status, period
      - customer.subscription.deleted  → revert to free
      - invoice.paid                   → reset period, clear past_due
      - invoice.payment_failed         → set status = past_due
    """
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    from app.billing import stripe_client
    stripe_client.configure(settings.stripe_secret_key)
    try:
        event = stripe_client.construct_webhook_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except Exception as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    event_type = event.type
    data = event.data.object

    # Use a new DB session for the webhook handler (no request-scoped session here)
    from app.db.session import async_session_factory

    async with async_session_factory() as db:
        if event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
            await _handle_subscription_event(db, data, event_type)
        elif event_type == "invoice.paid":
            await _handle_invoice_paid(db, data)
        elif event_type == "invoice.payment_failed":
            await _handle_invoice_payment_failed(db, data)
        else:
            logger.debug("Unhandled Stripe event type: %s", event_type)

        await db.commit()

    return {"received": True}


async def _handle_subscription_event(db: AsyncSession, stripe_sub, event_type: str) -> None:
    """Sync local subscription state from a Stripe subscription event."""
    stripe_sub_id = getattr(stripe_sub, "id", None)
    if not stripe_sub_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning("No local subscription found for stripe_subscription_id=%s", stripe_sub_id)
        return

    now = datetime.now(timezone.utc)

    if event_type == "customer.subscription.deleted":
        sub.status = "canceled"
        sub.tier = "free"
        sub.included_api_budget_microdollars = billing_service._budget_for_tier("free")
        sub.overage_allowed = billing_service._overage_for_tier("free")
        sub.updated_at = now
        logger.info("Subscription %s deleted; reverted org %s to free tier", stripe_sub_id, sub.org_id)
        return

    # Map Stripe status to our internal status
    stripe_status = getattr(stripe_sub, "status", "active")
    status_map = {
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "incomplete": "active",
        "trialing": "active",
    }
    sub.status = status_map.get(stripe_status, "active")

    # Sync period dates
    period_start = getattr(stripe_sub, "current_period_start", None)
    period_end = getattr(stripe_sub, "current_period_end", None)
    if period_start:
        sub.current_period_start = datetime.fromtimestamp(period_start, tz=timezone.utc)
    if period_end:
        sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

    sub.updated_at = now
    logger.info(
        "Subscription %s updated: status=%s period=%s–%s",
        stripe_sub_id, sub.status, sub.current_period_start, sub.current_period_end,
    )


async def _handle_invoice_paid(db: AsyncSession, invoice) -> None:
    """On invoice.paid: reset past_due flag."""
    customer_id = getattr(invoice, "customer", None)
    if not customer_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return

    if sub.status == "past_due":
        sub.status = "active"
        sub.updated_at = datetime.now(timezone.utc)
        logger.info("Invoice paid for customer %s; subscription status reset to active", customer_id)


async def _handle_invoice_payment_failed(db: AsyncSession, invoice) -> None:
    """On invoice.payment_failed: mark as past_due."""
    customer_id = getattr(invoice, "customer", None)
    if not customer_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return

    sub.status = "past_due"
    sub.updated_at = datetime.now(timezone.utc)
    logger.warning("Invoice payment failed for customer %s; subscription marked past_due", customer_id)
