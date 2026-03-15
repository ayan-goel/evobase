# Phase 3 — Discovery & Prompts for Structural Refactoring

Teach the discovery LLM to identify structural refactoring opportunities. Add refactor-specific guidance to both the system prompt and the patch generation prompt. Wire the new opportunity types through the orchestrator.

**Depends on:** Phase 1 (multi-file context) and Phase 2 (new file creation).

---

## Why this phase

Phases 1 and 2 built the plumbing — the agent can now read multiple files and create new ones. This phase turns on the actual intelligence: the LLM starts finding structural issues and generating cross-file patches. This is where users start seeing refactoring proposals in their PRs.

---

## Current state

- The discovery prompt in `apps/runner/runner/llm/prompts/discovery_prompts.py` defines the `type` enum as: `"performance"`, `"memory"`, `"tech_debt"`, `"error_handling"`, `"async_pattern"`, `"bundle_size"`, `"n_plus_one"`, `"dead_code"`, `"redundant_computation"`, `"sync_io"` (line 107–109). No structural types exist.
- The system prompt in `apps/runner/runner/llm/prompts/system_prompts.py` says "Every opportunity you identify must... be a real performance, correctness, or tech-debt issue" (line 445). There's no mention of structural quality.
- The patch prompt in `apps/runner/runner/llm/prompts/patch_prompts.py` says "File to change : {file_path}" (line 37) — singular. It has no guidance for multi-file edits or file creation.
- The orchestrator in `apps/runner/runner/agent/orchestrator.py` doesn't differentiate opportunity types — all go through the same patch → validate → select loop. No special handling is needed for structural types, but the event payloads should reflect the new types.

---

## New opportunity types

### `coupling`

**What it catches:** A module importing from another module's internals instead of its public API. Example: `import { hash } from "auth/internal/crypto"` when `auth/index.ts` re-exports it.

**How the LLM finds it:** During per-file analysis, the LLM sees import paths that reach into internal directories of other modules. No cross-file context needed at discovery time — the import path itself is the signal.

**Patch behavior:** Single-file fix (update the import path). Does not require Phase 2 (no new file creation). `related_files` is empty.

**Prompt guidance:** "Only flag coupling issues where a public re-export or barrel file already exists that the import should use instead. Do not flag imports where no cleaner alternative exists."

### `barrel_export`

**What it catches:** A directory with 3+ public modules and no `index.ts` / `__init__.py` / `mod.rs`, forcing consumers to import from deep paths.

**How the LLM finds it:** During per-file analysis, the LLM notices the file lives in a directory with many siblings and no barrel file. The repo map (shown during file selection) provides the directory structure.

**Patch behavior:** Creates one new file (`index.ts` or `__init__.py`). Requires Phase 2 (new file creation). `related_files` lists the sibling modules that should be re-exported.

**Prompt guidance:** "Only propose barrel exports for directories where at least 3 files are imported by code outside the directory. The barrel file should be under 20 lines."

### `extract_module`

**What it catches:** A helper function, utility, or constant that is defined in one file but used (or duplicated) in multiple files. Extracting it into a shared module removes duplication and clarifies ownership.

**How the LLM finds it:** During per-file analysis, the LLM sees a function that looks like a generic utility (no file-specific dependencies, pure input/output) colocated with domain logic. The LLM proposes extracting it.

**Patch behavior:** Multi-file: (1) create or append to a shared module, (2) remove the function from the source, (3) update the source file's import to use the shared module. Requires Phase 1 (multi-file context) and Phase 2 (new file creation). `related_files` lists the destination module (or directory, if the file doesn't exist yet).

**Prompt guidance:** "Only propose extraction for stateless, self-contained functions with no file-local dependencies. The function must be useful beyond its current file. Do not propose extracting functions that are only used once."

---

## Tasks

### 1. Add structural types to the discovery prompt

**File:** `apps/runner/runner/llm/prompts/discovery_prompts.py`

In `analysis_prompt()` (line 69), expand the `type` enum:

```
  - `type`: category — one of:
      "performance", "memory", "tech_debt", "error_handling",
      "async_pattern", "bundle_size", "n_plus_one", "dead_code",
      "redundant_computation", "sync_io",
      "coupling", "barrel_export", "extract_module"
```

Add a new section to the analysis prompt that explains the structural types and their constraints:

```
Structural refactoring types:
  - "coupling": a file imports from another module's internals when a
    public API (barrel/index file) exists. Only flag if the public
    re-export already exists.
  - "barrel_export": a directory with 3+ source files has no index/barrel
    file, forcing deep imports. The proposed barrel file must be under
    20 lines.
  - "extract_module": a stateless, self-contained helper function is
    defined alongside domain logic and could live in a shared module.
    Only flag if the function has no file-local dependencies and is
    useful beyond its current file.

For structural types, you MUST also provide:
  - `related_files`: list of repo-relative file paths involved in the
    refactoring (e.g. the destination module, the barrel file location,
    or the public API file). This field is required for "barrel_export"
    and "extract_module"; optional for "coupling".
```

---

### 2. Add structural quality focus to the system prompt

**File:** `apps/runner/runner/llm/prompts/system_prompts.py`

Add a structural quality section to `build_system_prompt()`, appended after the framework-specific focus:

```python
_STRUCTURAL_FOCUS = """
Structural quality (applies to all stacks):
- Import coupling: files importing from another module's internal paths
  when a public barrel/index re-export exists.
- Missing barrel files: directories with 3+ source files and no index
  file, forcing consumers to use deep import paths.
- Extraction candidates: stateless utility functions defined alongside
  domain logic that could live in a shared module for reuse.

Structural changes must be small and safe:
  - Extract only self-contained, stateless helpers — no class
    hierarchies, no refactoring entire modules.
  - Each structural change must be completable in under 100 lines
    of total change across all files.
  - Do not propose moves that require updating more than 2 import sites.
"""
```

Append `_STRUCTURAL_FOCUS` at the end of the prompt in `build_system_prompt()` (after line 450, before the closing triple-quote):

```python
return f"""...
{framework_focus}

{_STRUCTURAL_FOCUS}

Output format:
  ...
"""
```

---

### 3. Update the patch prompt for multi-file and create edits

**File:** `apps/runner/runner/llm/prompts/patch_prompts.py`

Expand `patch_generation_prompt()` to handle structural refactoring. The function already has the `extra_files` parameter from Phase 1. Now add content that tells the LLM how to use it:

When `extra_files` is non-empty, append after the primary file content block:

```
Additional files (you may also edit these or use them as reference):
---
File: {path}
{content}
---

MULTI-FILE EDITING RULES:
  - Each edit's "file" field must match one of the file paths shown above.
  - Edits are applied per-file, top-to-bottom within each file.
  - To CREATE a new file, add an edit with "create": true, an empty
    "search", and the full file content in "replace":
    {"file": "src/shared/utils.ts", "create": true, "search": "", "replace": "..."}
  - When moving code: first add it to the destination (create or modify),
    then remove it from the source, in that edit order.
  - Update imports in both files to reflect the move.
```

When the opportunity type is structural (`coupling`, `barrel_export`, `extract_module`), replace the hard constraints section with tighter guidance using the `constraint_summary_for_type()` helper from Phase 2:

```
HARD CONSTRAINTS — you MUST respect all of these:
  1. {constraint_text}
  2. Do NOT modify any test file (*test*, *spec*, *.test.*, *.spec.*).
  3. Do NOT modify config files (*.config.*, *.json, *.yaml, *.toml, *.env).
  4. Do NOT modify package.json or any lock file.
  5. Preserve all existing imports unless explicitly removing unused ones.
  6. When extracting code, ensure the source file still compiles after removal.
```

---

### 4. Parse `related_files` in the discovery analysis parser

**File:** `apps/runner/runner/agent/discovery.py`

This was partially done in Phase 1 (the parser reads `related_files` from JSON). Confirm it works end-to-end:

- If the LLM returns `"related_files": ["src/shared/utils.ts"]`, the `AgentOpportunity` should have `related_files=["src/shared/utils.ts"]`.
- If the LLM returns `"related_files": []` or omits it, `related_files` defaults to `[]`.

No new code needed — just confirm the Phase 1 implementation handles this. If not already done, add the parsing (see Phase 1, Task 2).

---

### 5. Wire structural types through the orchestrator

**File:** `apps/runner/runner/agent/orchestrator.py`

The orchestrator loop (line 156) does not need structural changes — it already processes all opportunity types uniformly. But update the event payloads to include `is_structural`:

In the `patch.approach.started` event (line 176), add:

```python
"is_structural": opp.is_structural,
```

In the `validation.verdict` event (line 309), add:

```python
"is_structural": opp.is_structural if hasattr(opp, 'is_structural') else False,
```

This allows the frontend and event consumers to visually distinguish structural proposals from performance fixes.

---

### 6. Update the file selection prompt with structural awareness

**File:** `apps/runner/runner/llm/prompts/discovery_prompts.py`

In `file_selection_prompt()` (line 15), add a line to the selection criteria that nudges the LLM to also look for structural issues:

```
  - Also consider directories with many files and no index/barrel file,
    and files with large utility sections that could be extracted.
```

This is a lightweight nudge — the main structural intelligence lives in the per-file analysis prompt (Task 1).

---

## Tests

### Discovery prompt tests

**File:** `apps/runner/tests/llm/test_prompts.py`

1. **`test_analysis_prompt_includes_structural_types`** — Call `analysis_prompt()` and assert the returned string contains `"coupling"`, `"barrel_export"`, and `"extract_module"`.

2. **`test_analysis_prompt_mentions_related_files`** — Assert the prompt contains `"related_files"`.

3. **`test_file_selection_prompt_mentions_structural`** — Call `file_selection_prompt()` and assert it contains "barrel" or "index" or "extracted".

### System prompt tests

**File:** `apps/runner/tests/llm/test_prompts.py`

4. **`test_system_prompt_includes_structural_focus`** — Call `build_system_prompt()` with a generic `DetectionResult()` and assert the output contains "Structural quality" and "barrel".

### Patch prompt tests

**File:** `apps/runner/tests/llm/test_prompts.py`

5. **`test_patch_prompt_with_extra_files_includes_multi_file_rules`** — Call `patch_generation_prompt()` with `extra_files={"lib/a.ts": "code"}` and assert the output contains "MULTI-FILE EDITING RULES" and "create" and `"lib/a.ts"`.

6. **`test_patch_prompt_without_extra_files_has_no_multi_file_section`** — Call with `extra_files=None` and assert "MULTI-FILE EDITING RULES" is NOT in the output.

7. **`test_patch_prompt_structural_type_uses_tighter_constraints`** — Call with `opportunity_type="extract_module"` and assert the constraints mention "3 files" and "100 lines" (not "5 files" and "200 lines").

### Discovery parsing tests

**File:** `apps/runner/tests/agent/test_discovery.py`

8. **`test_parse_opportunities_with_structural_type`** — Feed `_parse_opportunities()` JSON containing `"type": "extract_module"` and `"related_files": ["src/shared.ts"]`. Assert the resulting `AgentOpportunity` has `type="extract_module"`, `related_files=["src/shared.ts"]`, and `is_structural is True`.

### Orchestrator event tests

**File:** `apps/runner/tests/agent/test_orchestrator_events.py`

9. **`test_patch_started_event_includes_is_structural`** — Run a mocked agent cycle with a structural opportunity and assert the `patch.approach.started` event contains `"is_structural": True`.

---

## Files changed

| File | Change |
|------|--------|
| `apps/runner/runner/llm/prompts/discovery_prompts.py` | Add structural types to `analysis_prompt()`, nudge in `file_selection_prompt()` |
| `apps/runner/runner/llm/prompts/system_prompts.py` | Add `_STRUCTURAL_FOCUS` block to `build_system_prompt()` |
| `apps/runner/runner/llm/prompts/patch_prompts.py` | Multi-file editing rules, create-edit docs, structural constraint text |
| `apps/runner/runner/agent/orchestrator.py` | Add `is_structural` to event payloads |
| `apps/runner/tests/llm/test_prompts.py` | 7 new tests |
| `apps/runner/tests/agent/test_discovery.py` | 1 new test |
| `apps/runner/tests/agent/test_orchestrator_events.py` | 1 new test |

---

## Estimated cost impact

- **System prompt:** +~200 tokens per call (structural focus section). At ~26 LLM calls per run, that's +5,200 input tokens = +$0.016. Negligible.
- **Discovery prompt:** +~150 tokens per analysis call. At 10 analysis calls per run, that's +1,500 input tokens = +$0.005. Negligible.
- **Patch prompt (multi-file):** When `extra_files` is populated, +5K–10K input tokens per call. Assuming 5 structural opportunities per run, that's +25K–50K extra input tokens = +$0.08–$0.15.
- **Total estimated increase:** +$0.10–$0.17 per run (~5–8% on a $2 run).

---

## Prompt design principles

- **Be explicit about what NOT to propose.** "Only flag coupling issues where a public re-export already exists" is more useful than "find coupling issues." The LLM will over-report without tight scoping.
- **Structural constraints are tighter than performance constraints.** 3 files / 100 lines vs. 5 files / 200 lines. This reflects the higher risk of cross-file changes and keeps diffs reviewable.
- **"When moving code, first add to destination, then remove from source."** This edit ordering ensures the source file still compiles if the create edit fails — the original code is still there.
- **The `related_files` requirement is soft.** If the LLM omits it for a structural type, patchgen falls back to single-file mode (Phase 1 default). This avoids hard failures for a missing field.

---

## What this phase does NOT do

- Does not add import graph analysis to the repo map (Phase 4)
- Does not change hard constraint limits — only adds prompt-level guidance
- Does not add any new validation gates specific to structural changes
