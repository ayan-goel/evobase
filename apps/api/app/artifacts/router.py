"""Artifact endpoints for the Control Plane API.

Handles signed URL generation for artifact downloads and artifact
record creation from runner upload callbacks.

Artifacts are stored in Supabase Storage; users never access storage
directly. FastAPI generates time-limited signed URLs using the service
role key.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.models import Artifact, Organization, Proposal, Repository, Run
from app.db.session import get_db
from app.artifacts.schemas import (
    ArtifactUploadRequest,
    ArtifactUploadResponse,
    SignedUrlResponse,
)
from app.artifacts.storage import generate_signed_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{artifact_id}/signed-url", response_model=SignedUrlResponse)
async def get_artifact_signed_url(
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> SignedUrlResponse:
    """Generate a signed URL for downloading an artifact.

    Validates that the user has access to the artifact's proposal chain
    before generating the URL. Signed URLs expire after 1 hour.
    """
    result = await db.execute(
        select(Artifact).where(Artifact.id == artifact_id)
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found",
        )

    # Verify user has access through the proposal -> run -> repo -> org chain
    access_result = await db.execute(
        select(Proposal)
        .join(Run)
        .join(Repository)
        .join(Organization)
        .where(
            Proposal.id == artifact.proposal_id,
            Organization.owner_id == user_id,
        )
    )
    if not access_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found",
        )

    signed_url = await generate_signed_url(artifact.storage_path)

    return SignedUrlResponse(
        artifact_id=artifact.id,
        signed_url=signed_url,
        expires_in_seconds=3600,
    )


@router.post("/upload", response_model=ArtifactUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_artifact(
    body: ArtifactUploadRequest,
    db: AsyncSession = Depends(get_db),
) -> ArtifactUploadResponse:
    """Create an artifact record from a runner upload callback.

    This endpoint is called by the runner after uploading each artifact
    bundle (proposal.json, diff.patch, trace.json) for an accepted proposal.
    It is an internal callback — no user auth required.

    In MVP, the content field is accepted but not persisted (storage_path
    is the durable reference). In production, the runner would upload the
    file to Supabase Storage first, then call this endpoint with the path.
    """
    # Verify the proposal exists
    proposal_result = await db.execute(
        select(Proposal).where(Proposal.id == body.proposal_id)
    )
    proposal = proposal_result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proposal {body.proposal_id} not found",
        )

    artifact = Artifact(
        proposal_id=body.proposal_id,
        storage_path=body.storage_path,
        type=body.type,
    )
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)

    logger.info(
        "Created artifact %s (type=%s) for proposal %s",
        artifact.id, body.type, body.proposal_id,
    )

    return ArtifactUploadResponse(
        id=artifact.id,
        proposal_id=artifact.proposal_id,
        storage_path=artifact.storage_path,
        type=artifact.type,
        uploaded=True,
    )
