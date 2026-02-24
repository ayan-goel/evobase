"""GitHub webhook and PR creation endpoints.

Webhook endpoint is public (no auth dependency) but verifies the
X-Hub-Signature-256 header to confirm the payload came from GitHub.

PR creation is an authenticated user action.

Installation management endpoints allow users to list their GitHub App
installations and browse repos available via an installation.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from httpx import HTTPStatusError
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.models import GitHubInstallation, Organization, Proposal, Repository, Run
from app.db.session import get_db
from app.github.schemas import (
    CreatePrResponse,
    CreateRunPrRequest,
    CreateRunPrResponse,
    GitHubRepoItem,
    InstallationListResponse,
    InstallationReposResponse,
    InstallationResponse,
    LinkInstallationRequest,
    LinkInstallationResponse,
    WebhookResponse,
)
from app.github.service import create_pr_for_proposal, create_pr_for_run
from app.github.webhooks import parse_installation_event, verify_webhook_signature
from app.runs.service import create_and_enqueue_run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["github"])


# ---------------------------------------------------------------------------
# Webhooks (public, signature-verified)
# ---------------------------------------------------------------------------


@router.post("/webhooks", response_model=WebhookResponse)
async def handle_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Handle incoming GitHub App webhook events.

    Verifies the HMAC signature before processing. Handles:
    - installation (created/deleted): upsert or remove github_installations row
    - installation_repositories: upsert installation and log repo list
    - push: trigger a new run when a commit lands on the default branch
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
        action = event_data.get("action", "")
        inst_id = event_data.get("installation_id")

        if action == "created" and inst_id:
            result = await db.execute(
                select(GitHubInstallation).where(
                    GitHubInstallation.installation_id == inst_id
                )
            )
            existing = result.scalar_one_or_none()
            if not existing:
                db.add(
                    GitHubInstallation(
                        installation_id=inst_id,
                        account_login=event_data.get("account_login", ""),
                        account_id=event_data.get("account_id", 0),
                    )
                )
                await db.flush()
                logger.info("Persisted new installation %d", inst_id)

        elif action == "deleted" and inst_id:
            await db.execute(
                delete(GitHubInstallation).where(
                    GitHubInstallation.installation_id == inst_id
                )
            )
            logger.info("Removed installation %d", inst_id)

        elif x_github_event == "installation_repositories" and inst_id:
            result = await db.execute(
                select(GitHubInstallation).where(
                    GitHubInstallation.installation_id == inst_id
                )
            )
            if not result.scalar_one_or_none():
                db.add(
                    GitHubInstallation(
                        installation_id=inst_id,
                        account_login=event_data.get("account_login", ""),
                        account_id=event_data.get("account_id", 0),
                    )
                )
                await db.flush()

            logger.info(
                "installation_repositories event for %d: %d repos",
                inst_id,
                len(event_data.get("repositories", [])),
            )

        return WebhookResponse(received=True, event=x_github_event, action=action)

    if x_github_event == "push":
        ref = payload.get("ref", "")
        default_branch = payload.get("repository", {}).get("default_branch", "main")

        # Only react to pushes on the default branch
        if ref != f"refs/heads/{default_branch}":
            return WebhookResponse(received=True, event="push", action="non_default_branch")

        full_name = payload.get("repository", {}).get("full_name", "")
        head_sha = (payload.get("head_commit") or {}).get("id") or "HEAD"

        # Find the registered repository by its full name
        repo_result = await db.execute(
            select(Repository).where(Repository.github_full_name == full_name)
        )
        repo_row = repo_result.scalar_one_or_none()
        if not repo_row:
            logger.info("Push webhook: repo %s not registered, ignoring", full_name)
            return WebhookResponse(received=True, event="push", action="repo_not_found")

        # Skip if a run is already queued or running for this repo
        in_flight_result = await db.execute(
            select(Run).where(
                Run.repo_id == repo_row.id,
                Run.status.in_(["queued", "running"]),
            )
        )
        if in_flight_result.scalars().first():
            logger.info(
                "Push webhook: run already in flight for %s, skipping", full_name
            )
            return WebhookResponse(received=True, event="push", action="run_already_in_flight")

        run = await create_and_enqueue_run(db, repo_row.id, sha=head_sha)
        await db.commit()
        logger.info(
            "Push webhook: enqueued run %s for %s @ %s",
            run.id, full_name, head_sha[:7],
        )
        return WebhookResponse(received=True, event="push", action="run_enqueued")

    return WebhookResponse(received=True, event=x_github_event, action="ignored")


# ---------------------------------------------------------------------------
# Installation management (authenticated)
# ---------------------------------------------------------------------------


@router.get("/installations", response_model=InstallationListResponse)
async def list_installations(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> InstallationListResponse:
    """List GitHub App installations belonging to the current user."""
    result = await db.execute(
        select(GitHubInstallation).where(GitHubInstallation.user_id == user_id)
    )
    installations = result.scalars().all()
    return InstallationListResponse(
        installations=[
            InstallationResponse(
                id=str(inst.id),
                installation_id=inst.installation_id,
                account_login=inst.account_login,
                account_id=inst.account_id,
            )
            for inst in installations
        ],
        count=len(installations),
    )


@router.get(
    "/installations/{installation_id}/repos",
    response_model=InstallationReposResponse,
)
async def get_installation_repos(
    installation_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> InstallationReposResponse:
    """List repos available via a GitHub App installation.

    Calls the GitHub API with an installation token to fetch the repo list.
    """
    result = await db.execute(
        select(GitHubInstallation).where(
            GitHubInstallation.installation_id == installation_id,
            GitHubInstallation.user_id == user_id,
        )
    )
    installation = result.scalar_one_or_none()
    if not installation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Installation not found",
        )

    from app.github import client as github_client

    token = await github_client.get_installation_token(installation_id)
    raw_repos = await github_client.list_installation_repos(token)

    repos = [
        GitHubRepoItem(
            github_repo_id=r["id"],
            full_name=r["full_name"],
            name=r["name"],
            default_branch=r.get("default_branch", "main"),
            private=r.get("private", False),
        )
        for r in raw_repos
    ]

    return InstallationReposResponse(repos=repos, count=len(repos))


# ---------------------------------------------------------------------------
# Link installation to user (called from frontend after GitHub redirect)
# ---------------------------------------------------------------------------


@router.post("/link-installation", response_model=LinkInstallationResponse)
async def link_installation(
    body: LinkInstallationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> LinkInstallationResponse:
    """Associate a GitHub App installation with the current user.

    Called by the frontend after GitHub redirects back with installation_id.
    If the installation doesn't exist yet (webhook not received), creates it
    by fetching metadata from the GitHub API.
    """
    result = await db.execute(
        select(GitHubInstallation).where(
            GitHubInstallation.installation_id == body.installation_id
        )
    )
    installation = result.scalar_one_or_none()

    if installation:
        installation.user_id = user_id
    else:
        installation = GitHubInstallation(
            installation_id=body.installation_id,
            account_login=body.account_login or "",
            account_id=body.account_id or 0,
            user_id=user_id,
        )
        db.add(installation)

    await db.flush()
    logger.info("Linked installation %d to user %s", body.installation_id, user_id)

    return LinkInstallationResponse(
        installation_id=body.installation_id,
        linked=True,
    )


# ---------------------------------------------------------------------------
# PR creation (authenticated)
# ---------------------------------------------------------------------------


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
    """Create a GitHub pull request from a validated proposal."""
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

    if proposal.pr_url:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="PR already created for this proposal",
        )

    try:
        pr_url = await create_pr_for_proposal(repo, proposal)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except HTTPStatusError as exc:
        logger.error(
            "GitHub API error creating proposal PR for proposal %s: %s %s",
            proposal_id, exc.response.status_code, exc.response.text[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {exc.response.status_code} — {exc.response.text[:200]}",
        )

    proposal.pr_url = pr_url
    await db.commit()

    return CreatePrResponse(proposal_id=proposal.id, pr_url=pr_url)


@router.post(
    "/repos/{repo_id}/runs/{run_id}/create-pr",
    response_model=CreateRunPrResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_run_pr(
    repo_id: uuid.UUID,
    run_id: uuid.UUID,
    body: CreateRunPrRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> CreateRunPrResponse:
    """Create a single GitHub PR containing all selected proposals for a run."""
    result = await db.execute(
        select(Repository)
        .join(Organization)
        .where(Repository.id == repo_id, Organization.owner_id == user_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    result = await db.execute(
        select(Run).where(Run.id == run_id, Run.repo_id == repo_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    if run.pr_url:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="PR already created for this run",
        )

    if not body.proposal_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one proposal must be selected",
        )

    result = await db.execute(
        select(Proposal).where(
            Proposal.id.in_(body.proposal_ids),
            Proposal.run_id == run_id,
        )
    )
    proposals = list(result.scalars().all())

    if not proposals:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching proposals found for this run",
        )

    try:
        pr_url = await create_pr_for_run(repo, run, proposals)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except HTTPStatusError as exc:
        logger.error(
            "GitHub API error creating run PR for run %s: %s %s",
            run_id, exc.response.status_code, exc.response.text[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {exc.response.status_code} — {exc.response.text[:200]}",
        )

    run.pr_url = pr_url
    await db.commit()

    return CreateRunPrResponse(run_id=run.id, pr_url=pr_url)
