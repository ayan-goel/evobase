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

def file_selection_prompt(repo_map: str) -> str:
    """Prompt asking the LLM to select the most valuable files to analyse.

    The repo map is a compact directory listing with file sizes. The model
    picks 5–10 files that are most likely to contain optimisation opportunities
    based on naming patterns, location in the source tree, and file size
    (larger files tend to have more surface area).
    """
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

Respond with ONLY this JSON structure (no markdown, no commentary outside JSON):
{{
  "reasoning": "<your step-by-step thinking about which files to prioritise and why>",
  "files": ["<relative path 1>", "<relative path 2>", ...]
}}"""


# ---------------------------------------------------------------------------
# Stage 2: per-file opportunity analysis
# ---------------------------------------------------------------------------

def analysis_prompt(file_path: str, content: str) -> str:
    """Prompt asking the LLM to analyse a single file for opportunities.

    The model returns a structured list of opportunities, each with enough
    detail to drive patch generation without re-reading the file.
    """
    return f"""Analyse the following file and identify ALL concrete optimisation
opportunities. Focus only on issues that can be fixed with a targeted, small diff.

File: {file_path}
---
{content}
---

For each opportunity found, provide:
  - `type`: category — one of:
      "performance", "memory", "tech_debt", "error_handling",
      "async_pattern", "bundle_size", "n_plus_one", "dead_code",
      "redundant_computation", "sync_io"
  - `location`: "<filename>:<line_number>" pointing to the specific line.
  - `rationale`: why this is a problem and what the measurable impact is.
  - `approach`: the specific code change that would fix it.
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
      "approach": "<what to change>",
      "risk_level": "<low|medium|high>",
      "affected_lines": <integer>
    }}
  ]
}}

If you find no opportunities, return an empty array: {{"reasoning": "...", "opportunities": []}}"""
