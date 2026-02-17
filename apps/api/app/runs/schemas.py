"""Pydantic schemas for run endpoints."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# Valid run states follow a strict state machine:
# queued -> running -> completed | failed
RUN_STATUSES = {"queued", "running", "completed", "failed"}


class RunCreateRequest(BaseModel):
    """Payload for enqueuing a new optimization run."""

    sha: Optional[str] = Field(
        default=None,
        description="Commit SHA to run against. Defaults to HEAD of default branch.",
    )


class RunResponse(BaseModel):
    """Response schema for a single run."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    repo_id: uuid.UUID
    sha: Optional[str]
    status: str
    compute_minutes: Optional[float]
    trace_id: Optional[str] = None
    created_at: datetime


class RunListResponse(BaseModel):
    """List of runs for a repository."""

    runs: list[RunResponse]
    count: int
