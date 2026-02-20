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
    # repo_id is derived from proposal.run.repo_id — requires eager-loading Run.
    # Included here so the frontend can route directly to /repos/{repo_id}/...
    # without a separate lookup.
    repo_id: uuid.UUID
    diff: str
    summary: Optional[str]
    metrics_before: Optional[dict[str, Any]]
    metrics_after: Optional[dict[str, Any]]
    risk_score: Optional[float] = None
    confidence: Optional[str] = None
    created_at: datetime
    pr_url: Optional[str]
    framework: Optional[str] = None
    artifacts: list["ArtifactResponse"] = []
    discovery_trace: Optional[dict[str, Any]] = None
    patch_trace: Optional[dict[str, Any]] = None

    @classmethod
    def from_proposal(cls, proposal) -> "ProposalResponse":
        """Build a ProposalResponse, resolving repo_id from the eager-loaded run."""
        return cls(
            id=proposal.id,
            run_id=proposal.run_id,
            repo_id=proposal.run.repo_id,
            diff=proposal.diff,
            summary=proposal.summary,
            metrics_before=proposal.metrics_before,
            metrics_after=proposal.metrics_after,
            risk_score=proposal.risk_score,
            confidence=proposal.confidence,
            created_at=proposal.created_at,
            pr_url=proposal.pr_url,
            framework=proposal.framework,
            artifacts=[
                ArtifactResponse.model_validate(a) for a in proposal.artifacts
            ],
            discovery_trace=proposal.discovery_trace,
            patch_trace=proposal.patch_trace,
        )


class ArtifactResponse(BaseModel):
    """Response schema for a single artifact."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    # proposal_id is NULL for baseline artifacts (run-level, not tied to a proposal)
    proposal_id: Optional[uuid.UUID] = None
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
    """

    run_id: uuid.UUID
    diff: str = Field(..., min_length=1)
    summary: Optional[str] = None
    metrics_before: Optional[dict[str, Any]] = None
    metrics_after: Optional[dict[str, Any]] = None
    risk_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence: Optional[str] = Field(default=None)
    discovery_trace: Optional[dict[str, Any]] = None
    patch_trace: Optional[dict[str, Any]] = None
