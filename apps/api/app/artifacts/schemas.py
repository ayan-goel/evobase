"""Pydantic schemas for artifact endpoints."""

import uuid
from typing import Optional

from pydantic import BaseModel, Field


class SignedUrlResponse(BaseModel):
    """Response containing a signed URL for artifact download.

    Signed URLs are time-limited. The frontend must use them promptly.
    The service role key is used server-side to generate these; it is
    never exposed to the client.
    """

    artifact_id: uuid.UUID
    signed_url: Optional[str]  # None when Supabase is not configured
    expires_in_seconds: int = 3600


class ArtifactUploadRequest(BaseModel):
    """Request body for uploading a new artifact (called by the runner).

    The runner sends this for each bundle file after creating the proposal.
    In MVP, the content field carries the file text. In production, the
    runner would upload directly to Supabase Storage and send only the
    storage_path.
    """

    proposal_id: uuid.UUID
    storage_path: str = Field(..., min_length=1)
    type: str = Field(
        ...,
        description="Artifact type: 'proposal', 'diff', 'trace', 'log', 'baseline'",
    )
    content: Optional[str] = Field(
        default=None,
        description="File content (MVP only; omit when using direct storage upload)",
    )


class ArtifactUploadResponse(BaseModel):
    """Response after a successful artifact upload."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    proposal_id: uuid.UUID
    storage_path: str
    type: str
    uploaded: bool = True
