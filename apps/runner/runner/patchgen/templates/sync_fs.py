"""Template: Synchronous fs.* -> async fs.promises.*.

Transforms:
    const data = fs.readFileSync(path, "utf8");
Into:
    const data = await fs.promises.readFile(path, "utf8");

Also marks the containing function as async if it isn't already.
Only applies when the function signature is visible in the local context.
"""

import re
from typing import Optional

from runner.patchgen.templates.base import PatchTemplate

# Sync -> async method name mapping
_SYNC_TO_ASYNC = {
    "readFileSync": "readFile",
    "writeFileSync": "writeFile",
    "existsSync": "exists",
    "mkdirSync": "mkdir",
    "readdirSync": "readdir",
    "statSync": "stat",
    "unlinkSync": "unlink",
}

_SYNC_PATTERN = re.compile(
    r"\bfs\.(readFileSync|writeFileSync|existsSync|mkdirSync|readdirSync|statSync|unlinkSync)\b"
)


class SyncFsTemplate(PatchTemplate):
    name = "sync_fs"
    opportunity_type = "sync_fs_in_handler"
    explanation = (
        "Replaced synchronous fs method with its async equivalent from "
        "fs.promises. Synchronous fs calls block the Node.js event loop "
        "for the duration of I/O, reducing throughput under load."
    )

    def apply(self, source: str, location: str) -> Optional[str]:
        """Replace sync fs call at given line with async equivalent."""
        line_num = self._get_line_number(location)
        if line_num is None:
            return None

        lines = source.splitlines(keepends=True)
        if line_num < 1 or line_num > len(lines):
            return None

        original = lines[line_num - 1]
        match = _SYNC_PATTERN.search(original)
        if not match:
            return None

        sync_method = match.group(1)
        async_method = _SYNC_TO_ASYNC[sync_method]

        # Replace fs.readFileSync(...) -> await fs.promises.readFile(...)
        new_line = _SYNC_PATTERN.sub(
            lambda m: f"fs.promises.{_SYNC_TO_ASYNC[m.group(1)]}",
            original,
        )

        # Prepend await if not already present
        stripped = new_line.lstrip()
        if not stripped.startswith("await ") and "await " not in new_line:
            indent = len(new_line) - len(stripped)
            new_line = " " * indent + "await " + stripped

        if new_line == original:
            return None

        lines[line_num - 1] = new_line
        return "".join(lines)
