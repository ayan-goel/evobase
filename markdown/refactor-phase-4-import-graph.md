# Phase 4 — Import Graph in Repo Map

Build a lightweight import graph and inject it into the repo map so the file selection and discovery LLMs can reason about cross-file relationships: which files are heavily imported (good extraction candidates), which have no barrel file, and where coupling violations are most likely.

**Depends on:** None (can be built in parallel with Phases 1–3, but the discovery prompts from Phase 3 benefit most from this data).

---

## Why this phase

The current repo map in `apps/runner/runner/agent/repo_map.py` shows file names and line counts — purely structural. The LLM has no visibility into how files relate to each other. It can't distinguish a heavily-imported utility from a dead file, and it can't tell whether a directory already has a barrel export.

An import graph gives the LLM two critical signals:

1. **Fan-in** (how many files import this module) — high fan-in files are extraction candidates and change-risk indicators.
2. **Barrel coverage** (does this directory have an index file) — directories without barrels are `barrel_export` candidates.

This data turns the file selection stage from "guess which files look important by name" to "I can see which files are central to the codebase."

---

## Current state

- `build_repo_map()` in `apps/runner/runner/agent/repo_map.py` (line 65) walks the directory tree and emits lines like `  utils.ts  [42 lines]`. It has no import analysis.
- `SCANNABLE_EXTENSIONS` (line 31) defines which file types are included.
- `MAX_FILES_IN_MAP = 200` (line 63) caps the total files listed.
- The repo map is consumed by `file_selection_prompt()` in `apps/runner/runner/llm/prompts/discovery_prompts.py` (line 15), which passes it as the `repo_map` argument.

---

## Design decisions

### Scope: static regex extraction, not full AST parsing

A proper import graph requires language-specific AST parsers for every supported language. That's expensive to build and maintain. Instead, use regex-based extraction that handles the 90% case for common import syntaxes:

- **JavaScript/TypeScript:** `import ... from "..."`, `require("...")`
- **Python:** `import ...`, `from ... import ...`
- **Go:** `import "..."`, `import (...)`
- **Rust:** `use ...`, `mod ...`

Regex won't catch dynamic imports, re-exports through complex barrel files, or aliased paths configured in `tsconfig.json`. That's acceptable — the graph is a heuristic to guide the LLM, not a compiler. False negatives are fine; false positives are rare with the patterns below.

### Output format: compact annotations on existing map lines

Rather than a separate import graph section, annotate each file in the repo map with its fan-in count:

```
  utils.ts  [42 lines]  ← 8 importers
  helpers.ts  [15 lines]  ← 2 importers
  internal.ts  [30 lines]
```

And annotate directories with barrel coverage:

```
  components/  (no index file)
  services/  (has index.ts)
```

This keeps the repo map compact and doesn't require the LLM to cross-reference two separate data structures.

### Performance: single pass, bounded work

The import graph is built in a single pass over all scannable files. Each file is read once (up to the first 200 lines — imports are almost always at the top of the file) and its imports are extracted via regex. The total work is bounded by `MAX_FILES_IN_MAP` (200 files) × 200 lines = 40,000 lines scanned. This takes <1 second on any modern machine.

---

## Tasks

### 1. Add import extraction functions

**File:** `apps/runner/runner/agent/repo_map.py`

Add regex-based import extractors. Each returns a list of raw import specifiers (not resolved paths):

```python
import re

_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?\s+from\s+['"](.+?)['"]"""
    r"""|require\(\s*['"](.+?)['"]\s*\))""",
)

_PY_IMPORT_RE = re.compile(
    r"""(?:^from\s+([\w.]+)\s+import"""
    r"""|^import\s+([\w.]+))""",
    re.MULTILINE,
)

_GO_IMPORT_RE = re.compile(r'"([\w./\-]+)"')

_RUST_USE_RE = re.compile(r"^use\s+([\w:]+)", re.MULTILINE)


def _extract_imports(path: Path, max_lines: int = 200) -> list[str]:
    """Extract raw import specifiers from the top of a source file.

    Returns repo-relative-ish paths or package names. Resolution to actual
    file paths happens in _resolve_import().
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[:max_lines]
    except OSError:
        return []

    text = "\n".join(lines)
    suffix = path.suffix

    if suffix in (".js", ".jsx", ".mjs", ".ts", ".tsx", ".cjs"):
        matches = _JS_IMPORT_RE.findall(text)
        return [m[0] or m[1] for m in matches if m[0] or m[1]]
    if suffix in (".py", ".pyi"):
        matches = _PY_IMPORT_RE.findall(text)
        return [m[0] or m[1] for m in matches if m[0] or m[1]]
    if suffix == ".go":
        return _GO_IMPORT_RE.findall(text)
    if suffix == ".rs":
        return _RUST_USE_RE.findall(text)

    return []
```

---

### 2. Add import resolution (specifier to repo-relative path)

**File:** `apps/runner/runner/agent/repo_map.py`

Raw import specifiers like `"../utils"` or `"@/lib/helpers"` need to be resolved to repo-relative file paths to build the fan-in graph. This is a best-effort heuristic:

```python
def _resolve_import(
    specifier: str,
    importer_path: Path,
    repo_dir: Path,
    known_files: set[str],
) -> str | None:
    """Resolve an import specifier to a repo-relative file path.

    Returns None if the specifier is a third-party package (not in the repo)
    or cannot be resolved.
    """
    # Skip obvious third-party packages
    if not specifier.startswith(".") and not specifier.startswith("@/") and not specifier.startswith("src/"):
        # For Python: check if it matches a local module
        # For JS/TS: relative imports start with '.', project imports may use aliases
        # Heuristic: if the specifier matches a known file stem, it's local
        pass

    # Relative imports (JS/TS/Python)
    if specifier.startswith("."):
        resolved = (importer_path.parent / specifier).resolve()
        # Try with common extensions
        for ext in ("", ".ts", ".tsx", ".js", ".jsx", ".py"):
            candidate = str((resolved.parent / (resolved.name + ext)))
            rel = _try_relative(candidate, repo_dir)
            if rel and rel in known_files:
                return rel
        # Try as directory with index file
        for index in ("index.ts", "index.tsx", "index.js", "__init__.py"):
            candidate = resolved / index
            rel = _try_relative(str(candidate), repo_dir)
            if rel and rel in known_files:
                return rel

    return None


def _try_relative(abs_path: str, repo_dir: Path) -> str | None:
    """Convert an absolute path to a repo-relative string, or None."""
    try:
        return str(Path(abs_path).relative_to(repo_dir))
    except ValueError:
        return None
```

This resolution will miss alias paths (`@/...`, `~/...`, `#imports`) and monorepo cross-package imports. That's acceptable — the graph is a heuristic, and the most valuable signals come from relative imports which are the majority.

---

### 3. Build the fan-in graph

**File:** `apps/runner/runner/agent/repo_map.py`

Add a function that scans all files and builds a `dict[str, int]` mapping each file to its importer count:

```python
from collections import Counter

def _build_fan_in_graph(
    repo_dir: Path,
    scannable_files: list[tuple[str, Path]],
) -> dict[str, int]:
    """Build a fan-in count for each file: how many other files import it.

    Args:
        repo_dir: Repository root.
        scannable_files: List of (rel_path, abs_path) tuples for all scannable files.

    Returns:
        Mapping of repo-relative file path to the number of files that import it.
    """
    known_files = {rel for rel, _ in scannable_files}
    fan_in: Counter[str] = Counter()

    for rel_path, abs_path in scannable_files:
        specifiers = _extract_imports(abs_path)
        for spec in specifiers:
            resolved = _resolve_import(spec, abs_path, repo_dir, known_files)
            if resolved and resolved != rel_path:
                fan_in[resolved] += 1

    return dict(fan_in)
```

---

### 4. Detect barrel file coverage per directory

**File:** `apps/runner/runner/agent/repo_map.py`

Add a function that checks whether directories have index/barrel files:

```python
_BARREL_NAMES = {
    "index.ts", "index.tsx", "index.js", "index.jsx", "index.mjs",
    "__init__.py",
    "mod.rs",
}


def _has_barrel(dir_path: Path) -> bool:
    """Return True if the directory contains a barrel/index file."""
    try:
        return any(
            entry.name in _BARREL_NAMES
            for entry in dir_path.iterdir()
            if entry.is_file()
        )
    except PermissionError:
        return False
```

---

### 5. Annotate the repo map output

**File:** `apps/runner/runner/agent/repo_map.py`

Modify `build_repo_map()` to optionally include import graph data. Add a `include_imports: bool = False` parameter:

```python
def build_repo_map(repo_dir: Path, include_imports: bool = False) -> str:
```

When `include_imports` is True:

1. First collect all scannable files during the walk (store `(rel_path, abs_path)` pairs).
2. After the walk, call `_build_fan_in_graph()` to get fan-in counts.
3. Annotate file lines with fan-in counts when non-zero:

```
  utils.ts  [42 lines]  <- 8 importers
```

4. Annotate directory lines with barrel coverage:

```
  components/  (no index file)
  services/
```

The `(no index file)` annotation is only shown for directories that:
- Contain 3+ scannable files
- Do NOT have a barrel file
- Are at depth <= 2 (avoid noise from deep nested directories)

---

### 6. Enable import graph in file selection

**File:** `apps/runner/runner/agent/discovery.py`

In `_select_files()` (line 254), change the `build_repo_map()` call to include imports:

```python
repo_map = build_repo_map(repo_dir, include_imports=True)
```

No changes needed to the file selection prompt itself — the annotations are self-explanatory within the repo map format.

---

## Tests

### Import extraction tests

**File:** `apps/runner/tests/agent/test_repo_map.py`

1. **`test_extract_imports_js_esm`** — Write a file with `import { foo } from "./utils"` and `import bar from "../lib/bar"`. Assert both specifiers are extracted.

2. **`test_extract_imports_js_require`** — Write a file with `const x = require("./helper")`. Assert `"./helper"` is extracted.

3. **`test_extract_imports_python`** — Write a file with `from app.utils import helper` and `import os`. Assert `"app.utils"` and `"os"` are extracted.

4. **`test_extract_imports_go`** — Write a file with `import "myapp/internal/auth"`. Assert `"myapp/internal/auth"` is extracted.

5. **`test_extract_imports_rust`** — Write a file with `use crate::utils::helper;`. Assert `"crate::utils::helper"` is extracted.

6. **`test_extract_imports_respects_max_lines`** — Write a file with an import on line 1 and another on line 300. With `max_lines=200`, assert only the first is extracted.

7. **`test_extract_imports_handles_unreadable_file`** — Pass a nonexistent path, assert empty list returned (no exception).

### Import resolution tests

**File:** `apps/runner/tests/agent/test_repo_map.py`

8. **`test_resolve_relative_import_ts`** — Set up `src/a.ts` importing `"./b"` with `src/b.ts` existing. Assert resolution returns `"src/b.ts"`.

9. **`test_resolve_relative_import_with_extension`** — Import `"./b.ts"` resolves to `"src/b.ts"`.

10. **`test_resolve_directory_import_to_index`** — Import `"./utils"` where `src/utils/index.ts` exists. Assert resolution returns `"src/utils/index.ts"`.

11. **`test_resolve_third_party_returns_none`** — Import `"react"` or `"lodash"` returns `None`.

12. **`test_resolve_unresolvable_returns_none`** — Import `"./nonexistent"` with no matching file returns `None`.

### Fan-in graph tests

**File:** `apps/runner/tests/agent/test_repo_map.py`

13. **`test_fan_in_counts_importers_correctly`** — Set up 3 files where 2 import from the third. Assert fan-in for the third file is 2.

14. **`test_fan_in_excludes_self_imports`** — A file that imports itself (circular) does not count toward its own fan-in.

15. **`test_fan_in_empty_for_no_imports`** — A repo with no import statements produces an empty fan-in dict.

### Barrel detection tests

**File:** `apps/runner/tests/agent/test_repo_map.py`

16. **`test_has_barrel_true_for_index_ts`** — Directory with `index.ts` returns `True`.

17. **`test_has_barrel_true_for_init_py`** — Directory with `__init__.py` returns `True`.

18. **`test_has_barrel_false_for_no_index`** — Directory without any barrel file returns `False`.

### Repo map output tests

**File:** `apps/runner/tests/agent/test_repo_map.py`

19. **`test_repo_map_with_imports_annotates_fan_in`** — Call `build_repo_map(include_imports=True)` on a repo with known import relationships. Assert the output contains `<- N importers` for the imported file.

20. **`test_repo_map_with_imports_annotates_missing_barrel`** — A directory with 3+ files and no index should show `(no index file)` in the output.

21. **`test_repo_map_without_imports_has_no_annotations`** — Call `build_repo_map(include_imports=False)` and assert no `<-` or `(no index file)` annotations appear.

22. **`test_repo_map_with_imports_performance`** — Build the map for a repo with 200 files and assert it completes in under 2 seconds (regression guard).

---

## Files changed

| File | Change |
|------|--------|
| `apps/runner/runner/agent/repo_map.py` | Import extraction, resolution, fan-in graph, barrel detection, annotated output |
| `apps/runner/runner/agent/discovery.py` | Pass `include_imports=True` to `build_repo_map()` |
| `apps/runner/tests/agent/test_repo_map.py` | 22 new tests |

---

## Estimated cost impact

The import graph adds ~1.5–3K tokens to the repo map (annotations on ~200 file lines). This is sent once per run in the file selection call.

At $3.00/1M input tokens: +2,500 tokens = +$0.0075 per run. **Negligible.**

---

## Limitations and future work

### Known limitations

- **Alias paths (`@/`, `~/`, `#imports`) are not resolved.** These require reading `tsconfig.json` paths or `package.json` imports configuration. Adding this would require per-ecosystem config parsing. Skip for now — relative imports are the majority of internal imports.
- **Monorepo cross-package imports are not resolved.** An import like `@myorg/shared` from a monorepo workspace won't be resolved. This would require workspace awareness (reading root `package.json` workspaces config). Skip for now.
- **Python dotted imports (`from app.models import User`) use heuristic resolution.** The resolver checks if `app/models.py` or `app/models/__init__.py` exists. This works for standard project layouts but may miss unusual package structures.
- **Dynamic imports (`import("./lazy")`, `importlib.import_module()`) are not captured.** These are rare for the structural patterns we care about.

### Future enhancements (not in scope)

- **Circular dependency detection:** Walk the fan-in graph to find cycles. Requires storing the full edge list, not just fan-in counts. Would enable a `circular_dependency` opportunity type.
- **Dead export detection:** Combine fan-in data with export analysis to find functions/classes that are exported but never imported. Would enable a `dead_export` opportunity type.
- **Weighted fan-in:** Weight importers by their own importance (PageRank-style). Would produce a better file selection ranking. Overkill for now.
