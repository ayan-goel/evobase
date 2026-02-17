"""Pydantic schemas for GitHub integration endpoints."""

import uuid

from pydantic import BaseModel


class WebhookResponse(BaseModel):
    """Acknowledgement response for webhook events."""

    received: bool
    event: str
    action: str


class CreatePrResponse(BaseModel):
    """Response after successfully creating a PR from a proposal."""

    proposal_id: uuid.UUID
    pr_url: str
