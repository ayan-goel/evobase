"""Tests for runner/agent/repo_map.py."""

import pytest
from pathlib import Path
from runner.agent.repo_map import build_repo_map, MAX_DEPTH, SKIP_DIRS


class TestBuildRepoMap:
    def test_returns_string(self, tmp_path: Path) -> None:
        result = build_repo_map(tmp_path)
        assert isinstance(result, str)

    def test_includes_repo_name(self, tmp_path: Path) -> None:
        result = build_repo_map(tmp_path)
        assert tmp_path.name in result

    def test_includes_ts_files_with_line_counts(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "utils.ts"
        ts_file.write_text("const x = 1;\nconst y = 2;\n")
        result = build_repo_map(tmp_path)
        assert "utils.ts" in result
        assert "2 lines" in result

    def test_includes_js_files(self, tmp_path: Path) -> None:
        (tmp_path / "index.js").write_text("module.exports = {};")
        result = build_repo_map(tmp_path)
        assert "index.js" in result

    def test_includes_tsx_files(self, tmp_path: Path) -> None:
        (tmp_path / "App.tsx").write_text("export default function App() {}")
        result = build_repo_map(tmp_path)
        assert "App.tsx" in result

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "lodash.js").write_text("module")
        result = build_repo_map(tmp_path)
        assert "lodash.js" not in result

    def test_skips_dist(self, tmp_path: Path) -> None:
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "bundle.js").write_text("minified")
        result = build_repo_map(tmp_path)
        assert "bundle.js" not in result

    def test_includes_subdirectory_files(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "service.ts").write_text("export class S {}")
        result = build_repo_map(tmp_path)
        assert "src" in result
        assert "service.ts" in result

    def test_respects_depth_limit(self, tmp_path: Path) -> None:
        # Create a deep nested structure
        deep = tmp_path
        for level in range(MAX_DEPTH + 2):
            deep = deep / f"level{level}"
            deep.mkdir()
        (deep / "deep.ts").write_text("deep file")
        result = build_repo_map(tmp_path)
        # File at max depth + 2 should not appear
        assert "deep.ts" not in result

    def test_empty_repo(self, tmp_path: Path) -> None:
        result = build_repo_map(tmp_path)
        assert tmp_path.name in result  # at minimum shows the root

    def test_json_file_listed_without_line_count(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name": "test"}')
        result = build_repo_map(tmp_path)
        assert "package.json" in result
        # JSON files don't get line counts
        assert "[" not in result.split("package.json")[1].split("\n")[0]

    def test_includes_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("print('hello')\n")
        result = build_repo_map(tmp_path)
        assert "main.py" in result
        assert "1 lines" in result

    def test_includes_go_files(self, tmp_path: Path) -> None:
        (tmp_path / "main.go").write_text("package main\n\nfunc main() {}\n")
        result = build_repo_map(tmp_path)
        assert "main.go" in result

    def test_includes_rust_files(self, tmp_path: Path) -> None:
        (tmp_path / "lib.rs").write_text("fn main() {}\n")
        result = build_repo_map(tmp_path)
        assert "lib.rs" in result

    def test_includes_java_files(self, tmp_path: Path) -> None:
        (tmp_path / "App.java").write_text("public class App {}\n")
        result = build_repo_map(tmp_path)
        assert "App.java" in result

    def test_includes_ruby_files(self, tmp_path: Path) -> None:
        (tmp_path / "app.rb").write_text("puts 'hi'\n")
        result = build_repo_map(tmp_path)
        assert "app.rb" in result
