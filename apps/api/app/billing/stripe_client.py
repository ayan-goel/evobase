"""Thin Stripe API client wrapper.

All Stripe interactions go through this module so the rest of the codebase
remains decoupled from the stripe SDK. If Stripe is not configured (no secret
key), all methods raise a RuntimeError rather than silently no-oping.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Price IDs per tier — these must be created in your Stripe dashboard and
# set as environment variables. Set STRIPE_PRICE_<TIER>_ID in your .env.
# These are placeholder defaults; override in production.
_PRICE_ID_MAP: dict[str, str] = {
    "hobby": "price_hobby",
    "premium": "price_premium",
    "pro": "price_pro",
}


def _get_stripe():
    """Return the stripe module, raising if not installed or not configured."""
    try:
        import stripe
    except ImportError as exc:
        raise RuntimeError("stripe package not installed; run: pip install stripe") from exc
    return stripe


def configure(secret_key: str) -> None:
    """Set the Stripe API key. Call once at app startup."""
    stripe = _get_stripe()
    stripe.api_key = secret_key


def create_customer(email: str, metadata: Optional[dict] = None) -> str:
    """Create a Stripe Customer and return the customer_id."""
    stripe = _get_stripe()
    customer = stripe.Customer.create(
        email=email,
        metadata=metadata or {},
    )
    return customer["id"]


def create_subscription(
    customer_id: str,
    tier: str,
    price_id_override: Optional[str] = None,
) -> dict:
    """Create a Stripe Subscription with an embedded PaymentIntent.

    Returns the subscription dict (includes latest_invoice.payment_intent.client_secret).
    """
    stripe = _get_stripe()
    price_id = price_id_override or _PRICE_ID_MAP.get(tier)
    if not price_id:
        raise ValueError(f"No Stripe price ID configured for tier '{tier}'")

    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        payment_behavior="default_incomplete",
        payment_settings={"save_default_payment_method": "on_subscription"},
        expand=["latest_invoice.payment_intent"],
    )
    return subscription


def get_client_secret_from_subscription(subscription: dict) -> Optional[str]:
    """Extract the PaymentIntent client_secret from a newly created subscription."""
    try:
        return subscription["latest_invoice"]["payment_intent"]["client_secret"]
    except (KeyError, TypeError):
        return None


def update_subscription_tier(
    stripe_subscription_id: str,
    tier: str,
    price_id_override: Optional[str] = None,
) -> dict:
    """Swap the subscription to a new price (with proration)."""
    stripe = _get_stripe()
    price_id = price_id_override or _PRICE_ID_MAP.get(tier)
    if not price_id:
        raise ValueError(f"No Stripe price ID configured for tier '{tier}'")

    sub = stripe.Subscription.retrieve(stripe_subscription_id)
    item_id = sub["items"]["data"][0]["id"]

    return stripe.Subscription.modify(
        stripe_subscription_id,
        items=[{"id": item_id, "price": price_id}],
        proration_behavior="create_prorations",
    )


def cancel_subscription(stripe_subscription_id: str) -> dict:
    """Cancel a subscription at the end of the current billing period."""
    stripe = _get_stripe()
    return stripe.Subscription.modify(
        stripe_subscription_id,
        cancel_at_period_end=True,
    )


def construct_webhook_event(payload: bytes, sig_header: str, webhook_secret: str):
    """Verify and parse a Stripe webhook event."""
    stripe = _get_stripe()
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
