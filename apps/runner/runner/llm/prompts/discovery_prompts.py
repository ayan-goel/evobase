"""Discovery phase prompts.

Two-stage prompt chain:
  Stage 1 — File selection: given the repo map, pick which files to analyse.
  Stage 2 — Opportunity analysis: given a file's content, find all issues.

Each prompt embeds explicit JSON schema requirements so outputs can be
parsed without ambiguity.
"""

# ---------------------------------------------------------------------------
# Stage 1: file selection
# ---------------------------------------------------------------------------

def file_selection_prompt(repo_map: str, previously_found: str = "") -> str:
    """Prompt asking the LLM to select the most valuable files to analyse.

    The repo map is a compact directory listing with file sizes. The model
    picks 5–10 files that are most likely to contain optimisation opportunities
    based on naming patterns, location in the source tree, and file size
    (larger files tend to have more surface area).

    Args:
        repo_map: Compact directory tree with file line counts.
        previously_found: Pre-formatted string of (type, file) pairs already
            identified in prior runs. When non-empty, appended to the prompt
            so the model prioritises files with untapped potential.
    """
    seen_block = ""
    if previously_found:
        seen_block = f"""

The following issues have ALREADY been identified in previous runs.
Do NOT re-select files solely for these known issues — focus on files
that are likely to yield NEW, different findings:

{previously_found}

You may still select a file that appears above if you believe it has
other, different issues worth investigating."""

    return f"""Below is a directory tree of the repository with file line counts.

{repo_map}

Your task: identify the 5–10 files most likely to contain performance issues,
tech debt, or significant optimisation opportunities.

Selection criteria:
  - Prefer heavily-used utility files and shared modules over one-off scripts.
  - Prefer larger files (more lines = more opportunity surface).
  - Prefer files in hot code paths: route handlers, service classes, utility
    modules, data-transformation functions.
  - Skip test files, config files, generated files, and lock files.
  - Skip files in: node_modules/, dist/, build/, .next/, coverage/.
{seen_block}

Respond with ONLY this JSON structure (no markdown, no commentary outside JSON):
{{
  "reasoning": "<your step-by-step thinking about which files to prioritise and why>",
  "files": ["<relative path 1>", "<relative path 2>", ...]
}}"""


# ---------------------------------------------------------------------------
# Stage 2: per-file opportunity analysis
# ---------------------------------------------------------------------------

def analysis_prompt(
    file_path: str,
    content: str,
    already_found_in_file: str = "",
) -> str:
    """Prompt asking the LLM to analyse a single file for opportunities.

    The model returns a structured list of opportunities, each with enough
    detail to drive patch generation without re-reading the file.

    Args:
        file_path: Repo-relative path to the file being analysed.
        content: Full file content (possibly truncated for large files).
        already_found_in_file: Pre-formatted string of issues previously
            found in this specific file. When non-empty, appended to the
            prompt so the model avoids re-reporting them.
    """
    seen_block = ""
    if already_found_in_file:
        seen_block = f"""

IMPORTANT — The following issues in this file have ALREADY been identified
in previous runs. Do NOT report them again. Instead, look for different
patterns and deeper issues:

{already_found_in_file}
"""

    return f"""Analyse the following file and identify ALL concrete optimisation
opportunities. Focus only on issues that can be fixed with a targeted, small diff.

File: {file_path}
---
{content}
---
{seen_block}
For each opportunity found, provide:
  - `type`: category — one of:
      "performance", "memory", "tech_debt", "error_handling",
      "async_pattern", "bundle_size", "n_plus_one", "dead_code",
      "redundant_computation", "sync_io"
  - `location`: "<filename>:<line_number>" pointing to the specific line.
  - `rationale`: why this is a problem and what the measurable impact is.
  - `approaches`: 1–3 distinct, concrete implementation strategies for fixing the
    issue. List them from most recommended to least. Each entry must be a complete
    description that can drive patch generation without re-reading the file.
    Example: ["Wrap with useMemo and correct dependency array",
              "Extract computation to a module-level constant"]
  - `risk_level`: "low", "medium", or "high" (likelihood of breaking something).
  - `affected_lines`: approximate number of lines the fix would touch.

Respond with ONLY this JSON structure:
{{
  "reasoning": "<your detailed analysis of the file, what you found, and why each issue matters>",
  "opportunities": [
    {{
      "type": "<type>",
      "location": "<file>:<line>",
      "rationale": "<why it's a problem>",
      "approaches": ["<strategy 1>", "<strategy 2>"],
      "risk_level": "<low|medium|high>",
      "affected_lines": <integer>
    }}
  ]
}}

If you find no opportunities, return an empty array: {{"reasoning": "...", "opportunities": []}}"""
