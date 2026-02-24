"""Pydantic schemas for proposal endpoints."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PatchVariantResponse(BaseModel):
    """One approach variant that was generated and validated for a proposal."""

    approach_index: int
    approach_description: str
    diff: str
    is_selected: bool
    selection_reason: str = ""
    metrics_after: Optional[dict[str, Any]] = None
    patch_trace: Optional[dict[str, Any]] = None
    validation_result: Optional[dict[str, Any]] = None


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
    title: Optional[str] = None
    summary: Optional[str]
    metrics_before: Optional[dict[str, Any]]
    metrics_after: Optional[dict[str, Any]]
    risk_score: Optional[float] = None
    confidence: Optional[str] = None
    created_at: datetime
    pr_url: Optional[str]
    framework: Optional[str] = None
    patch_variants: list[PatchVariantResponse] = []
    selection_reason: Optional[str] = None
    approaches_tried: Optional[int] = None
    artifacts: list["ArtifactResponse"] = []
    discovery_trace: Optional[dict[str, Any]] = None
    patch_trace: Optional[dict[str, Any]] = None

    @classmethod
    def from_proposal(cls, proposal) -> "ProposalResponse":
        """Build a ProposalResponse, resolving repo_id from the eager-loaded run."""
        # Deserialize patch_variants from raw JSON dicts into PatchVariantResponse objects
        raw_variants = proposal.patch_variants or []
        patch_variants = []
        for v in raw_variants:
            if isinstance(v, dict):
                try:
                    patch_variants.append(PatchVariantResponse(**{
                        "approach_index": v.get("approach_index", 0),
                        "approach_description": v.get("approach_description", ""),
                        "diff": v.get("diff", ""),
                        "is_selected": v.get("is_selected", False),
                        "selection_reason": v.get("selection_reason", ""),
                        "metrics_after": v.get("metrics_after"),
                        "patch_trace": v.get("patch_trace"),
                        "validation_result": v.get("validation_result"),
                    }))
                except Exception:
                    pass

        return cls(
            id=proposal.id,
            run_id=proposal.run_id,
            repo_id=proposal.run.repo_id,
            diff=proposal.diff,
            title=proposal.title,
            summary=proposal.summary,
            metrics_before=proposal.metrics_before,
            metrics_after=proposal.metrics_after,
            risk_score=proposal.risk_score,
            confidence=proposal.confidence,
            created_at=proposal.created_at,
            pr_url=proposal.pr_url,
            framework=proposal.framework,
            patch_variants=patch_variants,
            selection_reason=proposal.selection_reason,
            approaches_tried=proposal.approaches_tried,
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
