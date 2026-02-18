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
    Coreloop does not auto-merge.
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


async def list_installation_repos(token: str) -> list[dict]:
    """List all repos accessible to an installation token."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_BASE}/installation/repositories",
            headers=_auth_headers(token),
        )
        response.raise_for_status()
        return response.json().get("repositories", [])


async def get_file_content(
    token: str,
    owner: str,
    repo: str,
    path: str,
    ref: str,
) -> dict | None:
    """GET /repos/{owner}/{repo}/contents/{path}?ref={ref}

    Returns {"content": decoded_str, "sha": str} or None when the file
    does not exist (404).
    """
    import base64

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}",
            headers=_auth_headers(token),
            params={"ref": ref},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        raw = base64.b64decode(data["content"].replace("\n", "")).decode("utf-8", errors="replace")
        return {"content": raw, "sha": data["sha"]}


async def put_file_content(
    token: str,
    owner: str,
    repo: str,
    path: str,
    message: str,
    new_content: str,
    branch: str,
    current_sha: str | None = None,
) -> None:
    """PUT /repos/{owner}/{repo}/contents/{path}

    Creates or updates a file. Pass *current_sha* when updating an
    existing file so GitHub can verify there are no race conditions.
    """
    import base64

    payload: dict = {
        "message": message,
        "content": base64.b64encode(new_content.encode()).decode(),
        "branch": branch,
    }
    if current_sha is not None:
        payload["sha"] = current_sha

    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}",
            headers=_auth_headers(token),
            json=payload,
        )
        response.raise_for_status()


async def delete_file(
    token: str,
    owner: str,
    repo: str,
    path: str,
    message: str,
    sha: str,
    branch: str,
) -> None:
    """DELETE /repos/{owner}/{repo}/contents/{path}"""
    async with httpx.AsyncClient() as client:
        response = await client.request(
            "DELETE",
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}",
            headers=_auth_headers(token),
            json={
                "message": message,
                "sha": sha,
                "branch": branch,
            },
        )
        response.raise_for_status()


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
