# Phase 2 — New File Creation Support

Extend the diff pipeline to handle creating new files via `/dev/null` diffs. Update the patch applicator and constraints to support refactor-type patches that move code between files.

**Depends on:** Phase 1 (multi-file patchgen context).

---

## Why this phase

Structural refactors like "extract this helper into its own module" or "add a barrel `index.ts`" require creating files that don't exist yet. The current pipeline assumes every file in a diff already exists on disk. This phase closes that gap at the diff generation, application, and constraint layers — without changing any LLM prompts or opportunity types.

---

## Current state

- `edits_to_unified_diff()` in `apps/runner/runner/agent/patchgen.py` (line 447) calls `difflib.unified_diff()` with the original file content. If the file doesn't exist, there's no content to diff against, and no mechanism to produce a "create file" diff.
- `_parse_patch_response_detailed()` in `patchgen.py` (line 501) iterates `touched_files` and looks up each path in `file_contents`. A new file won't be in `file_contents`, so it gets an empty string — but `edits_to_unified_diff()` isn't designed to handle "content was empty, this is a new file."
- `apply_diff()` in `apps/runner/runner/validator/patch_applicator.py` (line 31) uses `patch -p1` which natively understands `/dev/null` source headers — so the applicator already works for new files as long as the diff is formatted correctly.
- `enforce_constraints()` in `apps/runner/runner/patchgen/constraints.py` (line 53) applies the same limits to all patches. Refactor-type patches may need slightly different messaging (not limits) to guide the LLM toward staying small.

---

## Tasks

### 1. Support "create file" edits in the JSON schema

**File:** `apps/runner/runner/agent/patchgen.py`

The LLM's edit JSON currently has `file`, `search`, and `replace` keys. For new files, `search` is meaningless (there's no existing content to search in). Add support for an optional `"create": true` flag on an edit:

```json
{
  "file": "src/shared/helpers.ts",
  "create": true,
  "search": "",
  "replace": "export function formatDate(d: Date): string {\n  return d.toISOString();\n}\n"
}
```

When `create` is true:
- `search` must be empty (or absent)
- `replace` contains the full new file content
- The edit is not processed through `apply_search_replace()` — it's handled as a whole-file creation

---

### 2. Extend `edits_to_unified_diff()` for new files

**File:** `apps/runner/runner/agent/patchgen.py`

Add a new function `create_file_diff()` alongside the existing `edits_to_unified_diff()`:

```python
def create_file_diff(file_rel_path: str, new_content: str) -> str:
    """Produce a unified diff that creates a new file from scratch.

    Uses /dev/null as the source, which is the standard convention for
    file creation in unified diffs. `patch -p1` handles this natively.
    """
    if not new_content:
        return ""

    new_lines = new_content.splitlines(keepends=True)
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"

    diff_lines = [
        f"--- /dev/null\n",
        f"+++ b/{file_rel_path}\n",
        f"@@ -0,0 +1,{len(new_lines)} @@\n",
    ]
    diff_lines.extend(f"+{line}" for line in new_lines)
    return "".join(diff_lines)
```

---

### 3. Route create vs. modify edits in the response parser

**File:** `apps/runner/runner/agent/patchgen.py`

In `_parse_patch_response_detailed()` (line 501), split edits into two groups before processing:

```python
create_edits: dict[str, list[dict]] = {}
modify_edits: dict[str, list[dict]] = {}

for e in edits:
    file_path = str(e.get("file", ""))
    if e.get("create"):
        create_edits.setdefault(file_path, []).append(e)
    else:
        modify_edits.setdefault(file_path, []).append(e)
```

Process modify edits through the existing `edits_to_unified_diff()` path. Process create edits through `create_file_diff()`:

```python
for file_path, file_create_edits in create_edits.items():
    combined_content = "\n".join(e.get("replace", "") for e in file_create_edits)
    diff_chunk = create_file_diff(file_path, combined_content)
    if diff_chunk:
        all_diff_chunks.append(diff_chunk)
```

Update `touched_files` to include both created and modified files.

---

### 4. Validate that `patch -p1` handles `/dev/null` diffs

**File:** `apps/runner/runner/validator/patch_applicator.py`

The `patch` binary already handles `/dev/null` source diffs natively — this is standard unified diff behavior. **No code changes needed.** But add a targeted integration test to confirm this works in the sandbox environment (see Tests section).

The `--fuzz=3` flag on line 88 is safe for create diffs — there are no context lines to fuzz against when the source is `/dev/null`.

---

### 5. Add a `is_structural` helper to `AgentOpportunity`

**File:** `apps/runner/runner/agent/types.py`

Add a property that downstream code can use to branch behavior for structural refactors:

```python
STRUCTURAL_TYPES = frozenset({
    "extract_module", "barrel_export", "coupling", "colocation", "refactor",
})

@dataclass
class AgentOpportunity:
    ...

    @property
    def is_structural(self) -> bool:
        """True if this opportunity involves structural file reorganisation."""
        return self.type in STRUCTURAL_TYPES
```

This is used in Phase 3 but defined here so the type system is ready.

---

### 6. Add constraint guidance for structural patches

**File:** `apps/runner/runner/patchgen/constraints.py`

The existing hard limits (5 files, 200 lines) are already appropriate for structural refactors. No changes to the limits themselves. But add a utility that the patch prompt (Phase 3) can call to get constraint text tailored to the opportunity type:

```python
def constraint_summary_for_type(opportunity_type: str) -> str:
    """Return a human-readable constraint summary string for the given type.

    Structural types get tighter guidance text (prefer fewer files) while
    the hard limits stay the same.
    """
    if opportunity_type in ("extract_module", "barrel_export", "refactor"):
        return (
            "Touch at most 3 files (source + destination + one caller). "
            "Change at most 100 lines total. "
            "Do NOT modify test or config files."
        )
    return (
        "Touch at most 5 files (prefer 1). "
        "Change at most 200 lines total. "
        "Do NOT modify test or config files."
    )
```

This is a prompt-text helper, not a new hard constraint. The hard constraints remain unchanged.

---

## Tests

### Unit tests for `create_file_diff()`

**File:** `apps/runner/tests/agent/test_patchgen.py`

1. **`test_create_file_diff_produces_dev_null_header`** — Call `create_file_diff("src/new.ts", "const x = 1;\n")` and assert the output starts with `--- /dev/null` and contains `+++ b/src/new.ts`.

2. **`test_create_file_diff_has_correct_hunk_header`** — Assert the `@@` line reads `@@ -0,0 +1,N @@` where N matches the line count of the content.

3. **`test_create_file_diff_all_lines_are_additions`** — Assert every content line in the diff starts with `+`.

4. **`test_create_file_diff_returns_empty_for_empty_content`** — Pass empty string content, assert empty string returned.

5. **`test_create_file_diff_adds_trailing_newline`** — Pass content without trailing newline, assert the diff still has one.

### Integration tests for create edits in the parser

**File:** `apps/runner/tests/agent/test_patchgen.py`

6. **`test_parse_response_with_create_edit`** — Construct a JSON response with `"create": true`, pass to `_parse_patch_response_detailed()`, assert the resulting `AgentPatch.diff` contains a `/dev/null` diff for the new file.

7. **`test_parse_response_with_mixed_create_and_modify_edits`** — Return both a modify edit (against an existing file) and a create edit (new file). Assert the combined diff contains both a standard modify diff chunk and a `/dev/null` create diff chunk.

8. **`test_parse_response_create_edit_without_search_is_valid`** — Ensure a create edit with `"search": ""` is accepted and processed correctly.

### Integration test for `patch -p1` with `/dev/null` diffs

**File:** `apps/runner/tests/validator/test_patch_applicator.py`

9. **`test_apply_diff_creates_new_file`** — Generate a `/dev/null` diff using `create_file_diff()`, call `apply_diff()` on a temp repo directory, and assert the new file exists on disk with the expected content.

10. **`test_apply_diff_creates_new_file_in_subdirectory`** — Same as above but with a path like `src/shared/helpers.ts` where the subdirectory may or may not exist. Assert both the directory and file are created. (Note: `patch -p1` creates intermediate directories automatically.)

### Unit tests for `is_structural` and constraint helper

**File:** `apps/runner/tests/agent/test_types.py`

11. **`test_is_structural_true_for_extract_module`** — Assert `AgentOpportunity(type="extract_module", ...).is_structural` is `True`.

12. **`test_is_structural_false_for_performance`** — Assert `AgentOpportunity(type="performance", ...).is_structural` is `False`.

**File:** `apps/runner/tests/patchgen/test_constraints.py`

13. **`test_constraint_summary_for_structural_type`** — Assert the summary for `"extract_module"` mentions "3 files" and "100 lines".

14. **`test_constraint_summary_for_performance_type`** — Assert the summary for `"performance"` mentions "5 files" and "200 lines".

---

## Files changed

| File | Change |
|------|--------|
| `apps/runner/runner/agent/patchgen.py` | Add `create_file_diff()`, route create vs. modify edits in parser |
| `apps/runner/runner/agent/types.py` | Add `STRUCTURAL_TYPES` constant and `is_structural` property |
| `apps/runner/runner/patchgen/constraints.py` | Add `constraint_summary_for_type()` helper |
| `apps/runner/tests/agent/test_patchgen.py` | 8 new tests (create diff + mixed parsing) |
| `apps/runner/tests/validator/test_patch_applicator.py` | 2 new tests (patch applies create diffs) |
| `apps/runner/tests/agent/test_types.py` | 2 new tests (is_structural) |
| `apps/runner/tests/patchgen/test_constraints.py` | 2 new tests (constraint summary) |

---

## Risk notes

- **`patch -p1` directory creation:** The `patch` binary creates intermediate directories for new files automatically. If a particularly old or minimal `patch` version doesn't, the integration test (test 10) will catch this. Mitigation: add a `mkdir -p` pre-step in `apply_diff` if needed.
- **LLM producing invalid create edits:** The LLM may include `"search"` content in a create edit, or forget the `"create": true` flag. The parser should treat a create edit with non-empty `search` as a modify edit (fallback to existing behavior) rather than crashing. This is a defensive design choice.
- **Combined diff ordering:** The create diff chunks should appear after modify diff chunks in the combined output. This matters because `patch -p1` processes chunks in order — if a modify edit imports from a newly created file, the create must come first in the filesystem but the ordering in the diff doesn't affect `patch` behavior (it's per-file, not cross-file sequential).

---

## What this phase does NOT do

- Does not change any LLM prompts to ask for structural refactoring (Phase 3)
- Does not add new opportunity types to discovery (Phase 3)
- Does not add import graph analysis (Phase 4)
