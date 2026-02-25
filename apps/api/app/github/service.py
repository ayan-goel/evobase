"""GitHub service layer for high-level operations.

Orchestrates the multi-step PR creation workflow:
branch creation -> commit -> PR open.

This layer is the boundary between our domain models and the
GitHub API client. It translates proposals into GitHub API calls.
"""

import logging
import time

from unidiff import PatchSet

from app.db.models import Proposal, Repository, Run
from app.github import client as github_client

logger = logging.getLogger(__name__)


# Branch naming convention: coreloop/proposal-{short_id}
# Using a prefix makes it easy to identify Coreloop branches.
BRANCH_PREFIX = "coreloop/proposal-"
RUN_BRANCH_PREFIX = "coreloop/run-"


async def create_pr_for_proposal(repo: Repository, proposal: Proposal) -> str:
    """Create a full PR on GitHub for a validated proposal.

    Steps:
    1. Get an installation token for the repo
    2. Get the HEAD SHA of the default branch
    3. Create a new branch
    4. Commit the proposal's diff to the branch
    5. Open a PR back to the default branch

    Returns the PR URL (html_url).

    In MVP, this uses a simplified commit flow. The diff is included
    in the PR body as context since tree manipulation from raw diffs
    requires more complex blob/tree creation.
    """
    if not repo.github_repo_id:
        raise ValueError("Repository has no GitHub repo ID")
    if not repo.github_full_name:
        raise ValueError("Repository has no github_full_name")
    if "/" not in repo.github_full_name:
        raise ValueError(f"Invalid github_full_name: {repo.github_full_name!r}")
    if not repo.installation_id:
        raise ValueError("Repository has no GitHub App installation")

    owner, repo_name = repo.github_full_name.split("/", 1)
    installation_id = repo.installation_id

    token = await github_client.get_installation_token(installation_id)

    head_sha = await github_client.get_default_branch_sha(
        token, owner, repo_name, repo.default_branch
    )

    short_id = str(proposal.id)[:8]
    # Append a seconds-precision timestamp so retries after a mid-flight failure
    # never collide with a branch left behind by the previous attempt.
    ts = str(int(time.time()))[-6:]
    branch_name = f"{BRANCH_PREFIX}{short_id}-{ts}"

    await github_client.create_branch(
        token, owner, repo_name, branch_name, head_sha
    )

    # Apply the proposal diff to the branch before creating the PR
    if proposal.diff:
        commit_message = f"[Coreloop] {proposal.title or proposal.summary or 'Code optimization'}"
        await _commit_diff_to_branch(
            token=token,
            owner=owner,
            repo_name=repo_name,
            branch=branch_name,
            diff=proposal.diff,
            commit_message=commit_message,
            root_dir=repo.root_dir,
            parent_sha=head_sha,
        )

    pr_title = f"[Coreloop] {proposal.title or proposal.summary or 'Code optimization'}"
    pr_body = _build_pr_body(proposal)

    pr_data = await github_client.create_pull_request(
        token=token,
        owner=owner,
        repo=repo_name,
        title=pr_title,
        body=pr_body,
        head_branch=branch_name,
        base_branch=repo.default_branch,
    )

    return pr_data["html_url"]


async def create_pr_for_run(
    repo: Repository,
    run: Run,
    proposals: list[Proposal],
) -> str:
    """Create a single GitHub PR combining the diffs of all selected proposals.

    Commits each proposal's diff to a shared branch sequentially, then opens
    a PR with a combined description listing every proposal's summary.

    Returns the PR HTML URL.
    """
    if not repo.github_repo_id:
        raise ValueError("Repository has no GitHub repo ID")
    if not repo.github_full_name:
        raise ValueError("Repository has no github_full_name")
    if "/" not in repo.github_full_name:
        raise ValueError(f"Invalid github_full_name: {repo.github_full_name!r}")
    if not repo.installation_id:
        raise ValueError("Repository has no GitHub App installation")
    if not proposals:
        raise ValueError("No proposals selected for PR")

    owner, repo_name = repo.github_full_name.split("/", 1)

    token = await github_client.get_installation_token(repo.installation_id)

    head_sha = await github_client.get_default_branch_sha(
        token, owner, repo_name, repo.default_branch
    )

    short_id = str(run.id)[:8]
    # Append a seconds-precision timestamp so retries after a mid-flight failure
    # never collide with a branch left behind by the previous attempt.
    ts = str(int(time.time()))[-6:]
    branch_name = f"{RUN_BRANCH_PREFIX}{short_id}-{ts}"

    await github_client.create_branch(token, owner, repo_name, branch_name, head_sha)

    # Thread the parent SHA through sequential commits so we never re-query
    # the branch ref (avoids GitHub eventual-consistency race conditions).
    current_sha = head_sha
    for proposal in proposals:
        if not proposal.diff:
            continue
        commit_message = f"[Coreloop] {proposal.title or proposal.summary or 'Code optimization'}"
        current_sha = await _commit_diff_to_branch(
            token=token,
            owner=owner,
            repo_name=repo_name,
            branch=branch_name,
            diff=proposal.diff,
            commit_message=commit_message,
            root_dir=repo.root_dir,
            parent_sha=current_sha,
        )

    pr_title = f"[Coreloop] {len(proposals)} optimization{'s' if len(proposals) != 1 else ''}"
    pr_body = _build_run_pr_body(run, proposals)

    pr_data = await github_client.create_pull_request(
        token=token,
        owner=owner,
        repo=repo_name,
        title=pr_title,
        body=pr_body,
        head_branch=branch_name,
        base_branch=repo.default_branch,
    )

    return pr_data["html_url"]


async def _commit_diff_to_branch(
    token: str,
    owner: str,
    repo_name: str,
    branch: str,
    diff: str,
    commit_message: str,
    root_dir: str | None = None,
    parent_sha: str | None = None,
) -> str:
    """Parse the unified diff and commit all changed files atomically.

    Uses the Git Data API (blobs -> tree -> commit -> ref update) to create
    a single commit containing every file change in the diff. This avoids
    the 409 Conflict errors that occur when using the Contents API for
    sequential per-file commits (GitHub eventual consistency issue).

    File deletions are handled via the Contents API after the atomic commit
    since the Git Tree API with ``base_tree`` cannot remove files.

    Args:
        root_dir: Monorepo subdirectory the diff paths are relative to
            (e.g. ``"apps/web"``). When set, each path extracted from the
            diff is prefixed with this value before calling the GitHub API,
            producing the full repo-relative path.
        parent_sha: The commit SHA to use as the parent for the new commit.
            When provided, the branch HEAD is NOT re-queried — this avoids
            GitHub eventual-consistency races when chaining multiple commits.

    Returns:
        The SHA of the new commit (or *parent_sha* unchanged when the diff
        had no add/modify entries).
    """
    patch_set = PatchSet(diff)

    files_to_delete: list[str] = []
    tree_entries: list[dict] = []

    for pf in patch_set:
        rel_path = pf.path
        full_path = f"{root_dir.strip('/')}/{rel_path}" if root_dir else rel_path

        if pf.is_removed_file:
            files_to_delete.append(full_path)
            continue

        if pf.is_added_file:
            new_content = "".join(
                line.value for hunk in pf for line in hunk if line.line_type != "-"
            )
        else:
            file_data = await github_client.get_file_content(
                token, owner, repo_name, full_path, branch
            )
            if file_data is None:
                logger.warning(
                    "Could not fetch existing file '%s' from branch '%s' — "
                    "patch will be applied to an empty base. "
                    "Check that root_dir ('%s') is configured correctly for this repo.",
                    full_path, branch, root_dir,
                )
            original = file_data["content"] if file_data else ""
            new_content = _apply_patch_to_content(original, pf)

        blob_sha = await github_client.create_git_blob(
            token, owner, repo_name, new_content,
        )
        tree_entries.append({
            "path": full_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha,
        })

    # Resolve parent commit SHA (prefer caller-supplied to avoid re-querying)
    head_sha = parent_sha or await github_client.get_default_branch_sha(
        token, owner, repo_name, branch,
    )

    # Create the atomic commit if there are any adds/modifications
    if tree_entries:
        commit_data = await github_client.get_git_commit(
            token, owner, repo_name, head_sha,
        )
        base_tree_sha = commit_data["tree"]["sha"]

        new_tree_sha = await github_client.create_git_tree(
            token, owner, repo_name, tree_entries, base_tree_sha,
        )
        new_commit_sha = await github_client.create_git_commit(
            token, owner, repo_name, commit_message,
            new_tree_sha, [head_sha],
        )
        await github_client.update_branch_ref(
            token, owner, repo_name, branch, new_commit_sha,
        )
        head_sha = new_commit_sha

    # Handle deletions separately via the Contents API (rare case)
    for del_path in files_to_delete:
        file_data = await github_client.get_file_content(
            token, owner, repo_name, del_path, branch,
        )
        if file_data:
            await github_client.delete_file(
                token, owner, repo_name, del_path,
                commit_message, file_data["sha"], branch,
            )

    return head_sha


def _apply_patch_to_content(original: str, patched_file) -> str:
    """Apply hunks from *patched_file* to *original* and return the result.

    Iterates line-by-line through each hunk: context lines are kept as-is,
    ``+`` lines are included in the output, ``-`` lines are omitted.
    Lines outside any hunk (before the first or after the last) are preserved
    by rebuilding from the original via the hunk offset information.
    """
    original_lines = original.splitlines(keepends=True)
    result: list[str] = []
    original_pos = 0  # 0-based index into original_lines

    for hunk in patched_file:
        hunk_start = hunk.source_start - 1  # convert to 0-based

        # Preserve lines before this hunk
        result.extend(original_lines[original_pos:hunk_start])
        original_pos = hunk_start

        for line in hunk:
            if line.line_type == " ":  # context
                result.append(line.value)
                original_pos += 1
            elif line.line_type == "+":  # added
                result.append(line.value)
            elif line.line_type == "-":  # removed
                original_pos += 1

    # Preserve any remaining lines after the last hunk
    result.extend(original_lines[original_pos:])
    return "".join(result)


def _build_pr_body(proposal: Proposal) -> str:
    """Build the PR description from a proposal's evidence."""
    title = proposal.title or proposal.summary or "Code optimization"
    sections = [f"## {title}\n"]

    if proposal.summary and proposal.summary != title:
        sections.append(f"{proposal.summary}\n")

    if proposal.metrics_before and proposal.metrics_after:
        sections.append("### Metrics\n")
        sections.append("| Metric | Before | After |")
        sections.append("|--------|--------|-------|")
        all_keys = set(proposal.metrics_before.keys()) | set(proposal.metrics_after.keys())
        for key in sorted(all_keys):
            before = proposal.metrics_before.get(key, "—")
            after = proposal.metrics_after.get(key, "—")
            sections.append(f"| {key} | {before} | {after} |")
        sections.append("")

    sections.append("---")
    sections.append("*Generated by [Coreloop](https://github.com/ayangoel/coreloop) — autonomous code optimization.*")

    return "\n".join(sections)


def _build_run_pr_body(run: Run, proposals: list[Proposal]) -> str:
    """Build a combined PR description for a run-level PR."""
    count = len(proposals)
    sections = [f"## Coreloop Optimizations — Run `{str(run.id)[:8]}`\n"]
    sections.append(
        f"This PR contains {count} optimization"
        f"{'s' if count != 1 else ''} generated by Coreloop.\n"
    )

    for i, proposal in enumerate(proposals, 1):
        title = proposal.title or proposal.summary or "Optimization"
        sections.append(f"### {i}. {title}")
        # Include the full description only when it differs from the title
        if proposal.summary and proposal.summary != title:
            sections.append(f"\n{proposal.summary}")
        sections.append("")

    sections.append("---")
    sections.append("*Generated by [Coreloop](https://github.com/ayangoel/coreloop) — autonomous code optimization.*")

    return "\n".join(sections)
