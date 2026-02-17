"""GitHub API client for installation-scoped operations.

Uses httpx for async HTTP calls. All methods require an installation
access token, obtained via the GitHub App JWT exchange.

This client handles the three operations needed for PR creation:
1. Create a branch from the default branch
2. Create a commit with the patch diff
3. Open a pull request
"""

import httpx

from app.core.config import get_settings
from app.github.auth import create_app_jwt

GITHUB_API_BASE = "https://api.github.com"


async def get_installation_token(installation_id: int) -> str:
    """Exchange a GitHub App JWT for an installation access token.

    Installation tokens are scoped to the repos the user granted
    access to and expire after 1 hour.
    """
    app_jwt = create_app_jwt()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        return response.json()["token"]


async def create_branch(
    token: str,
    owner: str,
    repo: str,
    branch_name: str,
    from_sha: str,
) -> dict:
    """Create a new branch from a specific commit SHA."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs",
            headers=_auth_headers(token),
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": from_sha,
            },
        )
        response.raise_for_status()
        return response.json()


async def get_default_branch_sha(
    token: str,
    owner: str,
    repo: str,
    branch: str,
) -> str:
    """Get the latest commit SHA of a branch."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/ref/heads/{branch}",
            headers=_auth_headers(token),
        )
        response.raise_for_status()
        return response.json()["object"]["sha"]


async def create_commit_from_patch(
    token: str,
    owner: str,
    repo: str,
    branch: str,
    message: str,
    tree_sha: str,
    parent_sha: str,
) -> str:
    """Create a commit on a branch. Returns the new commit SHA.

    For MVP, we use the update-ref approach: create a blob/tree/commit
    chain and update the branch ref. This avoids needing to parse diffs
    into individual file operations.
    """
    async with httpx.AsyncClient() as client:
        # Create commit
        commit_resp = await client.post(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/commits",
            headers=_auth_headers(token),
            json={
                "message": message,
                "tree": tree_sha,
                "parents": [parent_sha],
            },
        )
        commit_resp.raise_for_status()
        commit_sha = commit_resp.json()["sha"]

        # Update branch ref to point to new commit
        await client.patch(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs/heads/{branch}",
            headers=_auth_headers(token),
            json={"sha": commit_sha},
        )

        return commit_sha


async def create_pull_request(
    token: str,
    owner: str,
    repo: str,
    title: str,
    body: str,
    head_branch: str,
    base_branch: str,
) -> dict:
    """Open a pull request. Returns the PR data including html_url.

    PR creation is always a user-initiated action in MVP.
    SelfOpt does not auto-merge.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls",
            headers=_auth_headers(token),
            json={
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch,
            },
        )
        response.raise_for_status()
        return response.json()


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
