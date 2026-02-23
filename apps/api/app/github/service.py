"""GitHub service layer for high-level operations.

Orchestrates the multi-step PR creation workflow:
branch creation -> commit -> PR open.

This layer is the boundary between our domain models and the
GitHub API client. It translates proposals into GitHub API calls.
"""

from unidiff import PatchSet

from app.db.models import Proposal, Repository, Run
from app.github import client as github_client


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
    branch_name = f"{BRANCH_PREFIX}{short_id}"

    await github_client.create_branch(
        token, owner, repo_name, branch_name, head_sha
    )

    # Apply the proposal diff to the branch before creating the PR
    if proposal.diff:
        commit_message = f"[Coreloop] {proposal.summary or 'Code optimization'}"
        await _commit_diff_to_branch(
            token=token,
            owner=owner,
            repo_name=repo_name,
            branch=branch_name,
            diff=proposal.diff,
            commit_message=commit_message,
        )

    pr_title = f"[Coreloop] {proposal.summary or 'Code optimization'}"
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
    branch_name = f"{RUN_BRANCH_PREFIX}{short_id}"

    await github_client.create_branch(token, owner, repo_name, branch_name, head_sha)

    for proposal in proposals:
        if not proposal.diff:
            continue
        commit_message = f"[Coreloop] {proposal.summary or 'Code optimization'}"
        await _commit_diff_to_branch(
            token=token,
            owner=owner,
            repo_name=repo_name,
            branch=branch_name,
            diff=proposal.diff,
            commit_message=commit_message,
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
) -> None:
    """Parse the unified diff and commit each changed file to the branch."""
    patch_set = PatchSet(diff)
    for pf in patch_set:
        # unidiff exposes .path which strips the a/ b/ prefixes
        path = pf.path

        if pf.is_removed_file:
            file_data = await github_client.get_file_content(
                token, owner, repo_name, path, branch
            )
            if file_data:
                await github_client.delete_file(
                    token, owner, repo_name, path,
                    commit_message, file_data["sha"], branch,
                )

        elif pf.is_added_file:
            new_content = "".join(
                line.value for hunk in pf for line in hunk if line.line_type != "-"
            )
            await github_client.put_file_content(
                token, owner, repo_name, path,
                commit_message, new_content, branch,
            )

        else:
            file_data = await github_client.get_file_content(
                token, owner, repo_name, path, branch
            )
            original = file_data["content"] if file_data else ""
            new_content = _apply_patch_to_content(original, pf)
            await github_client.put_file_content(
                token, owner, repo_name, path,
                commit_message, new_content, branch,
                current_sha=file_data["sha"] if file_data else None,
            )


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
    """Build the PR description from a proposal's evidence.

    Includes the optimization summary, metrics comparison, and risk score.
    This gives reviewers all the context needed for a fast review.
    """
    sections = ["## Coreloop Optimization Proposal\n"]

    if proposal.summary:
        sections.append(f"**Summary:** {proposal.summary}\n")

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

    if proposal.risk_score is not None:
        sections.append(f"**Risk Score:** {proposal.risk_score}\n")

    sections.append("---")
    sections.append("*This PR was generated by [Coreloop](https://github.com/ayangoel/coreloop) — an autonomous code optimization system.*")

    return "\n".join(sections)


def _build_run_pr_body(run: Run, proposals: list[Proposal]) -> str:
    """Build a combined PR description for a run-level PR."""
    sections = [f"## Coreloop Optimizations — Run `{str(run.id)[:8]}`\n"]
    sections.append(
        f"This PR contains {len(proposals)} optimization"
        f"{'s' if len(proposals) != 1 else ''} generated by Coreloop.\n"
    )

    for i, proposal in enumerate(proposals, 1):
        sections.append(f"### {i}. {proposal.summary or 'Optimization'}")
        if proposal.selection_reason:
            sections.append(f"> {proposal.selection_reason}")
        if proposal.risk_score is not None:
            sections.append(f"**Risk:** {round(proposal.risk_score * 100)}%")
        sections.append("")

    sections.append("---")
    sections.append("*This PR was generated by [Coreloop](https://github.com/ayangoel/coreloop) — an autonomous code optimization system.*")

    return "\n".join(sections)
