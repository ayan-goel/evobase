"""Proposal endpoints for the Control Plane API.

Handles retrieving validated optimization proposals with full evidence,
and accepts new proposals created by the runner after validation.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.db.models import Organization, Proposal, Repository, Run
from app.db.session import get_db
from app.proposals.schemas import (
    ProposalCreateRequest,
    ProposalListResponse,
    ProposalResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> ProposalResponse:
    """Get a single proposal with its artifacts and repo_id.

    Eagerly loads artifacts and the parent run so the frontend can display
    evidence links and route to the correct repo without a secondary fetch.
    """
    result = await db.execute(
        select(Proposal)
        .options(selectinload(Proposal.artifacts), selectinload(Proposal.run))
        .where(Proposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    # Verify user has access to this proposal's repo chain
    run_result = await db.execute(
        select(Run)
        .join(Repository)
        .join(Organization)
        .where(Run.id == proposal.run_id, Organization.owner_id == user_id)
    )
    if not run_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    return ProposalResponse.from_proposal(proposal)


@router.get("/by-run/{run_id}", response_model=ProposalListResponse)
async def list_proposals_by_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> ProposalListResponse:
    """List all proposals for a given run."""
    # Verify user has access to this run's repo chain
    run_result = await db.execute(
        select(Run)
        .join(Repository)
        .join(Organization)
        .where(Run.id == run_id, Organization.owner_id == user_id)
    )
    if not run_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    result = await db.execute(
        select(Proposal)
        .options(selectinload(Proposal.artifacts), selectinload(Proposal.run))
        .where(Proposal.run_id == run_id)
        .order_by(Proposal.created_at.desc())
    )
    proposals = result.scalars().all()
    return ProposalListResponse(
        proposals=[ProposalResponse.from_proposal(p) for p in proposals],
        count=len(proposals),
    )


@router.post("/create", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    body: ProposalCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """Create a new proposal record from a validated runner result.

    This endpoint is called by the runner after a candidate patch passes
    all acceptance gates. It does not require user auth — it is an internal
    callback protected by the network boundary (runner runs inside the same
    trust zone as the API).

    The runner should follow up with POST /artifacts/upload for each
    artifact bundle (proposal.json, diff.patch, trace.json).
    """
    # Verify the run exists
    run_result = await db.execute(
        select(Run).where(Run.id == body.run_id)
    )
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {body.run_id} not found",
        )

    proposal = Proposal(
        run_id=body.run_id,
        diff=body.diff,
        summary=body.summary,
        metrics_before=body.metrics_before,
        metrics_after=body.metrics_after,
        risk_score=body.risk_score,
        confidence=body.confidence,
        discovery_trace=body.discovery_trace,
        patch_trace=body.patch_trace,
    )
    db.add(proposal)
    await db.commit()

    # Re-fetch with artifacts + run eager-loaded to build the full response.
    result = await db.execute(
        select(Proposal)
        .options(selectinload(Proposal.artifacts), selectinload(Proposal.run))
        .where(Proposal.id == proposal.id)
    )
    proposal = result.scalar_one()

    logger.info(
        "Created proposal %s for run %s (confidence=%s)",
        proposal.id, body.run_id, body.confidence,
    )

    return ProposalResponse.from_proposal(proposal)
