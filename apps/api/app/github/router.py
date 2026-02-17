"""GitHub webhook and PR creation endpoints.

Webhook endpoint is public (no auth dependency) but verifies the
X-Hub-Signature-256 header to confirm the payload came from GitHub.

PR creation is an authenticated user action.
"""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.models import Organization, Proposal, Repository, Run
from app.db.session import get_db
from app.github.schemas import CreatePrResponse, WebhookResponse
from app.github.service import create_pr_for_proposal
from app.github.webhooks import parse_installation_event, verify_webhook_signature

router = APIRouter(prefix="/github", tags=["github"])


@router.post("/webhooks", response_model=WebhookResponse)
async def handle_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Handle incoming GitHub App webhook events.

    Verifies the HMAC signature before processing. Currently handles:
    - installation: when the App is installed or uninstalled
    - installation_repositories: when repos are added/removed

    Unknown events are acknowledged but ignored.
    """
    body = await request.body()

    if not verify_webhook_signature(body, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    payload = await request.json()

    if x_github_event in ("installation", "installation_repositories"):
        event_data = parse_installation_event(payload)
        # In MVP, we log the event. Full repo auto-connect comes later.
        return WebhookResponse(
            received=True,
            event=x_github_event,
            action=event_data.get("action", ""),
        )

    return WebhookResponse(
        received=True,
        event=x_github_event,
        action="ignored",
    )


@router.post(
    "/repos/{repo_id}/proposals/{proposal_id}/create-pr",
    response_model=CreatePrResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pr(
    repo_id: uuid.UUID,
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> CreatePrResponse:
    """Create a GitHub pull request from a validated proposal.

    This is an explicit user action — SelfOpt never auto-merges in MVP.
    The endpoint:
    1. Validates the user owns the repo
    2. Checks the proposal exists and has no PR yet
    3. Creates a branch, commits the diff, opens a PR
    4. Stores the PR URL in the database
    """
    # Verify repo access
    result = await db.execute(
        select(Repository)
        .join(Organization)
        .where(Repository.id == repo_id, Organization.owner_id == user_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    # Verify proposal exists and belongs to this repo
    result = await db.execute(
        select(Proposal)
        .join(Run)
        .where(Proposal.id == proposal_id, Run.repo_id == repo_id)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    # INVARIANT: proposals cannot have PRs created twice
    if proposal.pr_url:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="PR already created for this proposal",
        )

    pr_url = await create_pr_for_proposal(repo, proposal)

    proposal.pr_url = pr_url
    await db.commit()

    return CreatePrResponse(
        proposal_id=proposal.id,
        pr_url=pr_url,
    )
