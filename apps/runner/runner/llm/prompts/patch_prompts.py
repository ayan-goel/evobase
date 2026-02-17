"""Patch generation prompt.

Given an `AgentOpportunity` and the relevant file content, this prompt
asks the LLM to produce a unified diff that implements the fix.

The prompt embeds hard constraint reminders directly so the model has
no excuse for violating them. The diff format is specified precisely
to match what the system `patch -p1` utility expects.
"""


def patch_generation_prompt(
    file_path: str,
    content: str,
    opportunity_type: str,
    rationale: str,
    approach: str,
    risk_level: str,
) -> str:
    """Build the patch generation prompt for a single opportunity.

    Args:
        file_path: Repo-relative path to the file being changed.
        content: Current content of the file.
        opportunity_type: Category of the issue (e.g. "performance").
        rationale: Why this is a problem.
        approach: How to fix it.
        risk_level: "low" | "medium" | "high".

    Returns:
        A user-role message string ready to send to the LLM.
    """
    return f"""Generate a unified diff to fix the following issue.

File to change : {file_path}
Issue type     : {opportunity_type}
Risk level     : {risk_level}
Problem        : {rationale}
Approach       : {approach}

Current file content:
---
{content}
---

HARD CONSTRAINTS — you MUST respect all of these:
  1. The diff must be directly applicable with `patch -p1 -f`.
  2. Change at most 200 lines total (additions + removals).
  3. Touch at most 5 files (prefer touching only 1 file).
  4. Do NOT modify any test file (*test*, *spec*, *.test.*, *.spec.*).
  5. Do NOT modify config files (*.config.*, *.json, *.yaml, *.toml, *.env).
  6. Do NOT modify package.json or any lock file.
  7. Preserve all existing imports unless explicitly removing unused ones.

Unified diff format requirements:
  - Use `--- a/<file>` and `+++ b/<file>` headers.
  - Include `@@ -L,N +L,N @@` hunk headers with correct line numbers.
  - Each changed line must be prefixed with `-` (removed) or `+` (added).
  - Context lines have no prefix.
  - End the diff with a newline.

Respond with ONLY this JSON structure:
{{
  "reasoning": "<your detailed step-by-step thinking: what the code does now, why it's suboptimal, what the fix does, and why it's safe>",
  "diff": "<the complete unified diff string>",
  "explanation": "<concise one-paragraph explanation of the change for the PR description>",
  "touched_files": ["<list of files the diff modifies>"],
  "estimated_lines_changed": <integer>
}}

If you cannot produce a safe, correct diff, respond with:
{{
  "reasoning": "<why you cannot produce the diff>",
  "diff": null,
  "explanation": null,
  "touched_files": [],
  "estimated_lines_changed": 0
}}"""
