"""Tests for all 10 patch templates.

Each template class is tested with:
- A clear fixture input that should apply
- Verification that the transformation is correct
- A case where the template cannot apply (returns None)
"""

import pytest

from runner.patchgen.templates import (
    ArrayFindMapTemplate,
    DeadCodeTemplate,
    JsonParseCacheTemplate,
    LoopIntermediateTemplate,
    MemoizePureTemplate,
    RedundantSpreadTemplate,
    RegexInLoopTemplate,
    SetMembershipTemplate,
    StringConcatLoopTemplate,
    SyncFsTemplate,
    TEMPLATE_REGISTRY,
)


class TestSetMembershipTemplate:
    def test_replaces_not_equal_minus_one(self):
        source = 'if (arr.indexOf(x) !== -1) {\n  doSomething();\n}\n'
        result = SetMembershipTemplate().apply(source, "test.ts:1")
        assert result is not None
        assert "arr.includes(x)" in result
        assert "indexOf" not in result

    def test_replaces_gte_zero(self):
        source = 'const found = list.indexOf(item) >= 0;\n'
        result = SetMembershipTemplate().apply(source, "test.ts:1")
        assert result is not None
        assert "includes" in result

    def test_replaces_equal_minus_one_with_negation(self):
        source = 'if (arr.indexOf(x) === -1) {\n  notFound();\n}\n'
        result = SetMembershipTemplate().apply(source, "test.ts:1")
        assert result is not None
        assert "!arr.includes(x)" in result

    def test_no_match_returns_none(self):
        source = 'const idx = arr.indexOf(x);\n'
        result = SetMembershipTemplate().apply(source, "test.ts:1")
        assert result is None

    def test_invalid_line_returns_none(self):
        source = 'const x = 1;\n'
        result = SetMembershipTemplate().apply(source, "test.ts:99")
        assert result is None


class TestJsonParseCacheTemplate:
    def test_caches_repeated_parse(self):
        source = (
            'function process(raw) {\n'
            '  const a = JSON.parse(raw);\n'
            '  const b = JSON.parse(raw);\n'
            '  return a.x + b.y;\n'
            '}\n'
        )
        result = JsonParseCacheTemplate().apply(source, "test.ts:2")
        assert result is not None
        assert "_parsedJson" in result

    def test_single_parse_returns_none(self):
        source = 'const data = JSON.parse(input);\n'
        result = JsonParseCacheTemplate().apply(source, "test.ts:1")
        assert result is None


class TestStringConcatLoopTemplate:
    def test_replaces_concat_loop(self):
        source = (
            'function build(items) {\n'
            '  let result = "";\n'
            '  for (const item of items) {\n'
            '    result += item.name;\n'
            '  }\n'
            '  return result;\n'
            '}\n'
        )
        result = StringConcatLoopTemplate().apply(source, "test.ts:4")
        assert result is not None
        assert "map" in result
        assert "join" in result
        # Original loop should be removed
        assert 'result += item.name' not in result

    def test_no_init_returns_none(self):
        source = (
            'for (const x of arr) {\n'
            '  result += x;\n'
            '}\n'
        )
        result = StringConcatLoopTemplate().apply(source, "test.ts:2")
        assert result is None


class TestSyncFsTemplate:
    def test_replaces_readfilesync(self):
        source = 'const data = fs.readFileSync(path, "utf8");\n'
        result = SyncFsTemplate().apply(source, "test.ts:1")
        assert result is not None
        assert "await" in result
        assert "fs.promises.readFile" in result
        assert "readFileSync" not in result

    def test_replaces_writefilesync(self):
        source = 'fs.writeFileSync(outPath, content);\n'
        result = SyncFsTemplate().apply(source, "test.ts:1")
        assert result is not None
        assert "fs.promises.writeFile" in result

    def test_no_sync_call_returns_none(self):
        source = 'const data = await fs.readFile(path);\n'
        result = SyncFsTemplate().apply(source, "test.ts:1")
        assert result is None


class TestRegexInLoopTemplate:
    def test_hoists_regexp(self):
        source = (
            'for (const entry of entries) {\n'
            '  const ok = new RegExp("^[a-z]+$").test(entry);\n'
            '}\n'
        )
        result = RegexInLoopTemplate().apply(source, "test.ts:2")
        assert result is not None
        # Template generates a const with the pattern name, starts with "const re_" or "const _re"
        assert "const re" in result or "const _re" in result
        # The const should appear before the loop
        lines = result.splitlines()
        const_idx = next(i for i, l in enumerate(lines) if l.strip().startswith("const re"))
        for_idx = next(i for i, l in enumerate(lines) if "for (" in l)
        assert const_idx < for_idx

    def test_no_loop_returns_none(self):
        source = 'const match = new RegExp("pattern").test(str);\n'
        result = RegexInLoopTemplate().apply(source, "test.ts:1")
        assert result is None


class TestArrayFindMapTemplate:
    def test_pre_indexes_with_map(self):
        source = (
            'for (let i = 0; i < targets.length; i++) {\n'
            '  const match = data.find(d => d.id === targets[i]);\n'
            '}\n'
        )
        result = ArrayFindMapTemplate().apply(source, "test.ts:2")
        assert result is not None
        assert "new Map(" in result
        assert ".get(" in result
        assert ".find(" not in result

    def test_find_outside_loop_returns_none(self):
        source = 'const user = users.find(u => u.id === targetId);\n'
        result = ArrayFindMapTemplate().apply(source, "test.ts:1")
        assert result is None


class TestRedundantSpreadTemplate:
    def test_replaces_spread_with_assignment(self):
        source = (
            'for (const item of items) {\n'
            '  result = { ...result, [item.key]: item.value };\n'
            '}\n'
        )
        result = RedundantSpreadTemplate().apply(source, "test.ts:2")
        assert result is not None
        assert "{ ..." not in result
        assert "result[" in result or "result." in result

    def test_different_source_returns_none(self):
        source = (
            'for (const item of items) {\n'
            '  result = { ...other, [item.key]: item.value };\n'
            '}\n'
        )
        result = RedundantSpreadTemplate().apply(source, "test.ts:2")
        assert result is None


class TestMemoizePureTemplate:
    def test_wraps_pure_function(self):
        source = (
            'function compute(x) {\n'
            '  return x * x + 1;\n'
            '}\n'
        )
        result = MemoizePureTemplate().apply(source, "test.ts:1")
        assert result is not None
        assert "Map" in result
        assert "_computeCache" in result

    def test_function_with_side_effects_returns_none(self):
        source = (
            'function log(x) {\n'
            '  console.log(x);\n'
            '  return x;\n'
            '}\n'
        )
        result = MemoizePureTemplate().apply(source, "test.ts:1")
        assert result is None

    def test_async_function_returns_none(self):
        source = (
            'function fetchData(url) {\n'
            '  return await fetch(url);\n'
            '}\n'
        )
        result = MemoizePureTemplate().apply(source, "test.ts:1")
        assert result is None


class TestLoopIntermediateTemplate:
    def test_collapses_filter_map_chain(self):
        source = (
            'const names = items.filter(x => x.active).map(x => x.name);\n'
        )
        result = LoopIntermediateTemplate().apply(source, "test.ts:1")
        assert result is not None
        assert "reduce" in result
        assert ".filter(" not in result
        assert ".map(" not in result

    def test_no_chain_returns_none(self):
        source = 'const names = items.map(x => x.name);\n'
        result = LoopIntermediateTemplate().apply(source, "test.ts:1")
        assert result is None


class TestDeadCodeTemplate:
    def test_removes_dead_lines(self):
        source = (
            'function foo() {\n'
            '  return bar();\n'
            '  doSomething();\n'
            '  const x = 1;\n'
            '}\n'
        )
        result = DeadCodeTemplate().apply(source, "test.ts:2")
        assert result is not None
        assert "doSomething" not in result
        assert "const x = 1" not in result
        assert "return bar()" in result

    def test_no_return_returns_none(self):
        source = (
            'function foo() {\n'
            '  const x = doSomething();\n'
            '  return x;\n'
            '}\n'
        )
        result = DeadCodeTemplate().apply(source, "test.ts:2")
        assert result is None

    def test_nothing_after_return_returns_none(self):
        source = (
            'function foo() {\n'
            '  return bar();\n'
            '}\n'
        )
        result = DeadCodeTemplate().apply(source, "test.ts:2")
        assert result is None


class TestTemplateRegistry:
    def test_all_10_templates_registered(self):
        expected_types = {
            "set_membership",
            "json_parse_cache",
            "string_concat_loop",
            "sync_fs_in_handler",
            "regex_in_loop",
            "unindexed_find",
            "redundant_spread",
            "memoize_pure",
            "loop_intermediate",
            "dead_code",
        }
        assert set(TEMPLATE_REGISTRY.keys()) == expected_types

    def test_all_templates_have_name(self):
        for opp_type, cls in TEMPLATE_REGISTRY.items():
            instance = cls()
            assert instance.name, f"Template for {opp_type} has no name"

    def test_all_templates_have_explanation(self):
        for opp_type, cls in TEMPLATE_REGISTRY.items():
            instance = cls()
            assert instance.explanation, f"Template for {opp_type} has no explanation"
