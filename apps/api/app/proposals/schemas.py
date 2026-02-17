"""Pydantic schemas for proposal endpoints."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProposalResponse(BaseModel):
    """Response schema for a single proposal with full evidence."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    run_id: uuid.UUID
    diff: str
    summary: Optional[str]
    metrics_before: Optional[dict[str, Any]]
    metrics_after: Optional[dict[str, Any]]
    risk_score: Optional[float] = None
    confidence: Optional[str] = None
    created_at: datetime
    pr_url: Optional[str]
    artifacts: list["ArtifactResponse"] = []


class ArtifactResponse(BaseModel):
    """Response schema for a single artifact."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    proposal_id: uuid.UUID
    storage_path: str
    type: str
    created_at: datetime


class ProposalListResponse(BaseModel):
    """List of proposals for a run."""

    proposals: list[ProposalResponse]
    count: int


class ProposalCreateRequest(BaseModel):
    """Request body for creating a new proposal (called by the runner).

    The runner sends this after the candidate passes all acceptance gates.
    metrics_before/after are extracted from BaselineResult and CandidateResult
    using runner.packaging.proposal_bundler.extract_metrics.
    """

    run_id: uuid.UUID
    diff: str = Field(..., min_length=1)
    summary: Optional[str] = None
    metrics_before: Optional[dict[str, Any]] = None
    metrics_after: Optional[dict[str, Any]] = None
    risk_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence: Optional[str] = Field(
        default=None,
        description="Acceptance confidence level: 'high', 'medium', or 'low'",
    )
