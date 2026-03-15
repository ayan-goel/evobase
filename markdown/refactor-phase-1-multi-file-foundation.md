# Phase 1 — Multi-File Foundation

Add `related_files` to `AgentOpportunity`, extend patchgen to read multiple files into context, and update the patch prompt to accept multi-file content. No new opportunity types yet — this phase is purely plumbing so that Phases 2 and 3 have a solid foundation to build on.

---

## Why first

Every cross-file refactoring capability depends on two things: (1) the opportunity knowing which files are relevant, and (2) the patch generator being able to read and edit more than one file. Without this plumbing, none of the later phases are possible. This phase changes zero LLM behavior — it only widens the data flow.

---

## Current state

- `AgentOpportunity` has no field for related files. The `location` field encodes a single `"<file>:<line>"` string.
- `generate_agent_patch_with_diagnostics()` in `apps/runner/runner/agent/patchgen.py` reads exactly one file, parsed from `opportunity.location` (line 124). That file content is the only thing sent to the LLM.
- `patch_generation_prompt()` in `apps/runner/runner/llm/prompts/patch_prompts.py` accepts a single `file_path` and `content` string.
- `_parse_patch_response_detailed()` in `patchgen.py` reads edits that reference files by name. It already handles multiple files in the `touched_files` list (lines 536–555) — but only the primary file's content is available in `file_contents`, so edits targeting other files produce empty diffs.

---

## Tasks

### 1. Add `related_files` to `AgentOpportunity`

**File:** `apps/runner/runner/agent/types.py`

Add a new field to the `AgentOpportunity` dataclass:

```python
@dataclass
class AgentOpportunity:
    type: str
    location: str
    rationale: str
    risk_level: str
    approaches: list[str] = field(default_factory=list)
    affected_lines: int = 0
    related_files: list[str] = field(default_factory=list)   # NEW
    thinking_trace: Optional[ThinkingTrace] = None
```

Update `to_dict()` to include the new field:

```python
def to_dict(self) -> dict:
    return {
        ...
        "related_files": self.related_files,
        ...
    }
```

**Backward compatibility:** The field has a default value (`[]`), so existing code that constructs `AgentOpportunity` without `related_files` continues to work unchanged.

---

### 2. Parse `related_files` from discovery LLM response

**File:** `apps/runner/runner/agent/discovery.py`

In `_parse_opportunities()` (line 406), parse the new field from the LLM JSON response:

```python
related_files_raw = item.get("related_files", [])
related_files = [str(f) for f in related_files_raw if f] if isinstance(related_files_raw, list) else []

opp = AgentOpportunity(
    ...
    related_files=related_files,
    ...
)
```

**No prompt changes yet.** The discovery prompt does not ask for `related_files` in this phase — that happens in Phase 3. This just ensures the parser won't crash if the field is present (some models may spontaneously include it).

---

### 3. Extend patchgen to read related files

**File:** `apps/runner/runner/agent/patchgen.py`

In `generate_agent_patch_with_diagnostics()`, after reading the primary file (line 146), also read files from `opportunity.related_files`:

```python
# After reading primary file content (existing code at ~line 158):
file_contents: dict[str, str] = {file_rel_path: content}

for rel_path in (opportunity.related_files or []):
    extra_path = repo_dir / rel_path
    if not extra_path.is_file():
        logger.debug("Related file not found, skipping: %s", rel_path)
        continue
    try:
        extra_content = extra_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.debug("Cannot read related file %s: %s", rel_path, exc)
        continue
    if len(extra_content) > MAX_FILE_CHARS:
        extra_content = extra_content[:MAX_FILE_CHARS] + "\n\n... [file truncated at 20KB] ..."
    file_contents[rel_path] = extra_content
```

Then pass all file contents to `_call_patch_agent_with_diagnostics()`:

- Change the function signature to accept `file_contents: dict[str, str]` instead of `file_rel_path: str` + `content: str`.
- Or (simpler, less invasive): pass `file_contents` as a new parameter and keep the existing `file_rel_path` + `content` for the primary file.

The second approach is less invasive. Add `extra_file_contents: dict[str, str] | None = None` to `_call_patch_agent_with_diagnostics()`.

---

### 4. Update patch prompt to include multiple files

**File:** `apps/runner/runner/llm/prompts/patch_prompts.py`

Add a new function for multi-file context and update the existing function to use it:

```python
def patch_generation_prompt(
    file_path: str,
    content: str,
    opportunity_type: str,
    rationale: str,
    approach: str,
    risk_level: str,
    extra_files: dict[str, str] | None = None,
) -> str:
```

When `extra_files` is non-empty, append a section after the primary file content:

```
Additional file context (read-only reference — you may also edit these files):
---
File: {extra_path}
{extra_content}
---
```

The existing prompt format for the primary file remains unchanged. The extra files are appended as additional context.

**Important:** The "File to change" header should be updated to "Primary file" when extra files are present, and a note added clarifying that edits may target any of the provided files.

---

### 5. Pass all file contents to the response parser

**File:** `apps/runner/runner/agent/patchgen.py`

In `_call_patch_agent_with_diagnostics()`, the call to `_parse_patch_response_detailed()` already accepts a `file_contents` dict (line 322–326). Currently it only contains the primary file:

```python
file_contents={file_rel_path: content}
```

Update this to merge in the extra files:

```python
all_contents = {file_rel_path: content}
if extra_file_contents:
    all_contents.update(extra_file_contents)

patch, failure_stage, failure_reason = _parse_patch_response_detailed(
    response.content,
    response.thinking_trace,
    file_contents=all_contents,
)
```

This is already how `_parse_patch_response_detailed` works — it iterates over `touched_files` and looks up content in the `file_contents` dict. With this change, edits targeting related files will produce correct diffs.

---

### 6. Emit `related_files` in discovery events

**File:** `apps/runner/runner/agent/discovery.py`

In `_serialise_file_opportunities_for_event()` (line 204), add `related_files` to the event payload:

```python
return [
    {
        ...
        "related_files": opp.related_files,
    }
    for opp in opps
]
```

And in `orchestrator.py`, include it in the `patch.approach.started` event data (line 176):

```python
_emit("patch.approach.started", "patch", {
    ...
    "related_files": opp.related_files,
})
```

---

## Tests

**File:** `apps/runner/tests/agent/test_patchgen.py`

### New unit tests

1. **`test_related_files_content_passed_to_prompt`** — Create an opportunity with `related_files=["lib/helper.ts"]`, write both files to `tmp_path`, mock the provider, and assert the LLM prompt contains both file contents.

2. **`test_edits_targeting_related_file_produce_valid_diff`** — Return LLM edits that target a related file (not the primary). Assert the resulting `AgentPatch.diff` contains diff headers for the related file and `touched_files` includes it.

3. **`test_missing_related_file_is_skipped_gracefully`** — Set `related_files=["nonexistent.ts"]` and assert the patch generation does not fail — it proceeds with only the primary file.

4. **`test_related_file_truncated_at_max_chars`** — Write a related file larger than `MAX_FILE_CHARS` and assert the content passed to the LLM is truncated.

**File:** `apps/runner/tests/agent/test_types.py`

5. **`test_agent_opportunity_related_files_defaults_to_empty`** — Construct an `AgentOpportunity` without `related_files` and assert it defaults to `[]`.

6. **`test_agent_opportunity_to_dict_includes_related_files`** — Construct with `related_files=["a.ts"]` and assert `to_dict()` output includes the field.

**File:** `apps/runner/tests/agent/test_discovery.py`

7. **`test_parse_opportunities_extracts_related_files`** — Feed `_parse_opportunities()` a JSON response containing `related_files` and assert the resulting `AgentOpportunity` objects have the correct values.

8. **`test_parse_opportunities_handles_missing_related_files`** — Feed JSON without the `related_files` key and assert it defaults to `[]`.

---

## Files changed

| File | Change |
|------|--------|
| `apps/runner/runner/agent/types.py` | Add `related_files` field + update `to_dict()` |
| `apps/runner/runner/agent/discovery.py` | Parse `related_files` from LLM JSON + update event serialisation |
| `apps/runner/runner/agent/patchgen.py` | Read related files, pass to prompt and response parser |
| `apps/runner/runner/agent/orchestrator.py` | Include `related_files` in event payloads |
| `apps/runner/runner/llm/prompts/patch_prompts.py` | Add `extra_files` parameter to `patch_generation_prompt()` |
| `apps/runner/tests/agent/test_patchgen.py` | 4 new tests |
| `apps/runner/tests/agent/test_types.py` | 2 new tests |
| `apps/runner/tests/agent/test_discovery.py` | 2 new tests |

---

## Estimated cost impact

+~$0.03 per cross-file patch generation call (extra input tokens from related file content). With 0 cross-file opportunities in this phase (no discovery prompt changes), the cost impact is **zero** until Phase 3 is shipped.

---

## What this phase does NOT do

- Does not add new opportunity types (Phase 3)
- Does not support creating new files (Phase 2)
- Does not change any LLM prompts to ask for structural refactoring (Phase 3)
- Does not add import graph analysis (Phase 4)
