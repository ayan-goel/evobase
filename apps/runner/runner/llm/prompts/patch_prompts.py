"""Patch generation prompt.

Given an `AgentOpportunity` and the relevant file content, this prompt asks the
LLM to produce a list of search/replace edits rather than a raw unified diff.

The LLM only needs to quote the text it wants to change (which it already has
in its context window) and write the replacement — it never has to count line
numbers or reproduce `@@ -L,N +L,N @@` hunk headers. The unified diff is then
generated programmatically by `patchgen.py` using `difflib`, which guarantees a
syntactically correct diff that `patch -p1` can always apply.
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
    return f"""Fix the following issue by providing search/replace edits.

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
  1. Change at most 200 lines total (additions + removals).
  2. Touch at most 5 files (prefer touching only 1 file).
  3. Do NOT modify any test file (*test*, *spec*, *.test.*, *.spec.*).
  4. Do NOT modify config files (*.config.*, *.json, *.yaml, *.toml, *.env).
  5. Do NOT modify package.json or any lock file.
  6. Preserve all existing imports unless explicitly removing unused ones.

Search/replace format:
  - Each edit has a "search" block (exact text from the file) and a "replace" block
    (what to put instead).
  - The "search" block MUST appear verbatim in the file — copy it character-for-character,
    including all whitespace and indentation.
  - Include at least 5 lines of surrounding context in "search" to make it unique.
  - If the same block appears more than once, include more context until it is unique.
  - You may provide multiple edits for the same file (they are applied top-to-bottom).
  - An empty "replace" deletes the matched block.

Respond with ONLY this JSON structure:
{{
  "reasoning": "<your detailed step-by-step thinking: what the code does now, why it's suboptimal, what the fix does, and why it's safe>",
  "title": "<5-8 word imperative-mood title for this change, like a git commit subject line, e.g. 'Memoize Badge to cut redundant re-renders'>",
  "edits": [
    {{
      "file": "{file_path}",
      "search": "<exact text from the file to replace>",
      "replace": "<new code>"
    }}
  ],
  "explanation": "<concise one-paragraph explanation of the change for the PR description>",
  "estimated_lines_changed": <integer>
}}

If you cannot produce a safe, correct edit, respond with:
{{
  "reasoning": "<why you cannot produce the edit>",
  "title": null,
  "edits": [],
  "explanation": null,
  "estimated_lines_changed": 0
}}"""
