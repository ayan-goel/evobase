"""Pydantic schemas for billing endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SubscriptionResponse(BaseModel):
    tier: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    # Usage expressed as a percentage (0–100+) — no dollar amounts exposed.
    usage_pct: float
    overage_active: bool
    monthly_spend_limit_microdollars: Optional[int] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None


class UsageRunRow(BaseModel):
    run_id: str
    created_at: datetime
    api_cost_microdollars: int
    billed_microdollars: int
    call_count: int


class UsageResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_api_cost_microdollars: int
    total_billed_microdollars: int
    included_api_budget_microdollars: int
    usage_pct: float
    runs: list[UsageRunRow]


class CheckoutRequest(BaseModel):
    tier: str  # "hobby" | "premium" | "pro"


class CheckoutResponse(BaseModel):
    client_secret: str
    publishable_key: str


class UpgradeRequest(BaseModel):
    tier: str


class SpendLimitRequest(BaseModel):
    # Pass null/None to remove the limit entirely.
    monthly_spend_limit_microdollars: Optional[int] = Field(default=None, ge=0)


class BillingConfigResponse(BaseModel):
    publishable_key: str
