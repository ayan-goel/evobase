"""Unit tests for individual heuristic detectors."""

from pathlib import Path

from runner.scanner.heuristics import scan_heuristics


class TestIndexOfHeuristic:
    def test_indexof_not_equal_minus_one(self):
        code = 'if (arr.indexOf(x) !== -1) {}'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "set_membership" for o in opps)

    def test_indexof_greater_equal_zero(self):
        code = 'if (arr.indexOf(x) >= 0) {}'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "set_membership" for o in opps)

    def test_indexof_greater_minus_one(self):
        code = 'if (arr.indexOf(x) > -1) {}'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "set_membership" for o in opps)

    def test_indexof_equal_minus_one(self):
        code = 'if (arr.indexOf(x) === -1) {}'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "set_membership" for o in opps)

    def test_indexof_less_than_zero(self):
        code = 'if (arr.indexOf(x) < 0) {}'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "set_membership" for o in opps)

    def test_no_false_positive_on_includes(self):
        code = 'if (arr.includes(x)) {}'
        opps = scan_heuristics(Path("test.js"), code)
        assert not any(o.type == "set_membership" for o in opps)


class TestJsonParseHeuristic:
    def test_detects_json_parse(self):
        code = 'const data = JSON.parse(raw);'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "json_parse_cache" for o in opps)

    def test_detects_json_parse_with_spaces(self):
        code = 'const data = JSON.parse( rawStr );'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "json_parse_cache" for o in opps)

    def test_no_false_positive_on_stringify(self):
        code = 'const str = JSON.stringify(obj);'
        opps = scan_heuristics(Path("test.js"), code)
        assert not any(o.type == "json_parse_cache" for o in opps)


class TestSyncFsHeuristic:
    def test_readfile_sync(self):
        code = 'const data = fs.readFileSync("file.txt");'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "sync_fs_in_handler" for o in opps)

    def test_writefile_sync(self):
        code = 'fs.writeFileSync("out.txt", data);'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "sync_fs_in_handler" for o in opps)

    def test_exists_sync(self):
        code = 'if (fs.existsSync(path)) {}'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "sync_fs_in_handler" for o in opps)

    def test_no_false_positive_on_async(self):
        code = 'const data = await fs.readFile("file.txt");'
        opps = scan_heuristics(Path("test.js"), code)
        assert not any(o.type == "sync_fs_in_handler" for o in opps)


class TestStringConcatHeuristic:
    def test_concat_in_for_loop(self):
        code = 'for (const x of arr) {\n  result += x;\n}'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "string_concat_loop" for o in opps)

    def test_concat_in_while_loop(self):
        code = 'while (running) {\n  output += line;\n}'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "string_concat_loop" for o in opps)

    def test_concat_outside_loop_not_flagged(self):
        code = 'let greeting = "hello";\ngreeting += " world";'
        opps = scan_heuristics(Path("test.js"), code)
        assert not any(o.type == "string_concat_loop" for o in opps)


class TestRegexInLoopHeuristic:
    def test_new_regexp_in_loop(self):
        code = 'for (const x of arr) {\n  new RegExp("pattern").test(x);\n}'
        opps = scan_heuristics(Path("test.js"), code)
        assert any(o.type == "regex_in_loop" for o in opps)

    def test_regex_outside_loop_not_flagged(self):
        code = 'const re = /pattern/g;\nre.test(str);'
        opps = scan_heuristics(Path("test.js"), code)
        assert not any(o.type == "regex_in_loop" for o in opps)


class TestOpportunityMetadata:
    def test_location_includes_line_number(self):
        code = 'line1\nconst data = JSON.parse(raw);\nline3'
        opps = scan_heuristics(Path("src/utils.ts"), code)
        assert opps[0].location == "src/utils.ts:2"

    def test_source_is_heuristic(self):
        code = 'const data = JSON.parse(raw);'
        opps = scan_heuristics(Path("test.js"), code)
        assert all(o.source == "heuristic" for o in opps)

    def test_risk_score_in_valid_range(self):
        code = 'arr.indexOf(x) !== -1\nJSON.parse(s)\nfs.readFileSync("f")'
        opps = scan_heuristics(Path("test.js"), code)
        for opp in opps:
            assert 0.0 <= opp.risk_score <= 1.0
