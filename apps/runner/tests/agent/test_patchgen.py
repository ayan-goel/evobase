"""Tests for runner/agent/patchgen.py.

Uses mocked LLM providers. No real API calls are made.
Validates search/replace parsing, diff generation, constraint enforcement, and
self-correction.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from runner.agent.patchgen import (
    PATCHGEN_FAILURE_STAGE_JSON_PARSE,
    PATCHGEN_FAILURE_STAGE_SEARCH_NOT_FOUND,
    _build_correction_feedback,
    _parse_file_from_location,
    _parse_patch_response,
    _strip_leading_overlap,
    _strip_trailing_overlap,
    apply_search_replace,
    edits_to_unified_diff,
    generate_agent_patch,
    generate_agent_patch_with_diagnostics,
)
from runner.agent.types import AgentOpportunity
from runner.llm.types import LLMConfig, LLMResponse, ThinkingTrace


# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------

_UTILS_TS_CONTENT = "const x = 1;\nconst re = /abc/;\nreturn x;\n"

_BIG_FILE_CONTENT = "code\n"


def _make_config() -> LLMConfig:
    return LLMConfig(provider="anthropic", model="claude-sonnet-4-5", api_key="test")


def _make_trace() -> ThinkingTrace:
    return ThinkingTrace(
        model="claude-sonnet-4-5", provider="anthropic",
        reasoning="Let me think about this...",
        prompt_tokens=50, completion_tokens=80,
    )


def _make_opportunity(location: str = "src/utils.ts:10") -> AgentOpportunity:
    return AgentOpportunity(
        type="performance",
        location=location,
        rationale="regex in loop",
        risk_level="low",
        approaches=["hoist regex"],
    )


def _make_valid_edits(file_path: str = "src/utils.ts") -> list[dict]:
    """Return edits that can be applied to _UTILS_TS_CONTENT."""
    return [
        {
            "file": file_path,
            "search": "const x = 1;\nconst re = /abc/;\nreturn x;\n",
            "replace": "const x = 1;\nconst _re = /abc/;\nreturn x;\n",
        }
    ]


def _make_big_edits(file_path: str = "big.ts") -> list[dict]:
    """Return edits that will produce >200 lines changed when diffed."""
    big_replacement = "\n".join(f"line{i}" for i in range(205)) + "\n"
    return [{"file": file_path, "search": _BIG_FILE_CONTENT, "replace": big_replacement}]


def _make_response(
    edits: list[dict] | None = None,
    explanation: str = "Fixed regex",
) -> LLMResponse:
    return LLMResponse(
        content=json.dumps({
            "reasoning": "I hoisted the regex",
            "edits": edits if edits is not None else _make_valid_edits(),
            "explanation": explanation,
            "estimated_lines_changed": 2,
        }),
        thinking_trace=_make_trace(),
    )


# ---------------------------------------------------------------------------
# Unit tests: apply_search_replace
# ---------------------------------------------------------------------------

class TestApplySearchReplace:
    def test_replaces_unique_block(self) -> None:
        content = "line1\nline2\nline3\n"
        result = apply_search_replace(content, "line2\n", "replaced\n")
        assert result == "line1\nreplaced\nline3\n"

    def test_raises_when_search_not_found(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            apply_search_replace("line1\nline2\n", "missing\n", "x\n")

    def test_raises_when_search_appears_multiple_times(self) -> None:
        content = "foo\nfoo\nfoo\n"
        with pytest.raises(ValueError, match="appears 3 times"):
            apply_search_replace(content, "foo\n", "bar\n")

    def test_raises_on_empty_search(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            apply_search_replace("content", "", "replacement")

    def test_empty_replace_deletes_block(self) -> None:
        content = "keep\nremove\nkeep\n"
        result = apply_search_replace(content, "remove\n", "")
        assert result == "keep\nkeep\n"

    def test_does_not_apply_second_match_when_ambiguous(self) -> None:
        with pytest.raises(ValueError):
            apply_search_replace("a\na\n", "a\n", "b\n")

    def test_strips_trailing_overlap(self) -> None:
        """Replace block includes multi-line tail already after the search block."""
        content = "header\nold_code\nreturn 1;\nreturn 2;\nfooter\n"
        result = apply_search_replace(
            content,
            "old_code\n",
            "new_code\nreturn 1;\nreturn 2;\n",
        )
        assert result == "header\nnew_code\nreturn 1;\nreturn 2;\nfooter\n"

    def test_single_line_trailing_overlap_not_stripped(self) -> None:
        """A 1-line overlap is too likely to be coincidence — leave it alone."""
        content = "header\nold_code\nreturn 1;\nfooter\n"
        result = apply_search_replace(
            content,
            "old_code\n",
            "new_code\nreturn 1;\n",
        )
        # Not stripped: the LLM may genuinely want to duplicate `return 1;`
        assert result == "header\nnew_code\nreturn 1;\nreturn 1;\nfooter\n"

    def test_strips_leading_overlap(self) -> None:
        """Replace block includes multi-line head already before the search block."""
        content = "header\ncontext1\ncontext2\nold_code\nfooter\n"
        result = apply_search_replace(
            content,
            "old_code\n",
            "context1\ncontext2\nnew_code\n",
        )
        assert result == "header\ncontext1\ncontext2\nnew_code\nfooter\n"

    def test_single_line_leading_overlap_not_stripped(self) -> None:
        """A 1-line overlap on the leading side is also not stripped."""
        content = "header\ncontext\nold_code\nfooter\n"
        result = apply_search_replace(
            content,
            "old_code\n",
            "context\nnew_code\n",
        )
        assert result == "header\ncontext\ncontext\nnew_code\nfooter\n"

    def test_full_replace_overlap_not_stripped_to_empty(self) -> None:
        """If every line of replace overlaps, we must not turn it into an empty deletion.

        Pure deletions would have been written as replace="" directly, so when
        a non-empty replace would be completely stripped, assume the LLM
        intended the content and leave it alone.
        """
        content = "a\nb\nc\nd\ne\n"
        # replace is "c\nd\n"; after search = "c\nd\ne\n" → full overlap of both lines
        result = apply_search_replace(
            content,
            "b\n",
            "c\nd\n",
        )
        # Not stripped because best_overlap == len(replace_lines)
        assert result == "a\nc\nd\nc\nd\ne\n"

    def test_no_overlap_passthrough(self) -> None:
        """When there is no overlap, the replace is used as-is."""
        content = "line1\nline2\nline3\n"
        result = apply_search_replace(content, "line2\n", "REPLACED\n")
        assert result == "line1\nREPLACED\nline3\n"

    def test_partial_line_not_stripped(self) -> None:
        """Partial line matches must NOT be treated as overlap."""
        content = "header\nold_code\nreturn 1;\nfooter\n"
        result = apply_search_replace(
            content,
            "old_code\n",
            "new_code\nreturn 1\n",  # no semicolon — partial line match
        )
        assert result == "header\nnew_code\nreturn 1\nreturn 1;\nfooter\n"

    def test_strips_multiline_trailing_overlap(self) -> None:
        """Overlap detection handles multiple trailing lines."""
        content = "a\nSEARCH\nb\nc\nd\n"
        result = apply_search_replace(
            content,
            "SEARCH\n",
            "NEW\nb\nc\n",
        )
        assert result == "a\nNEW\nb\nc\nd\n"

    def test_strips_multiline_leading_overlap(self) -> None:
        """Overlap detection handles multiple leading lines."""
        content = "a\nb\nc\nSEARCH\nd\n"
        result = apply_search_replace(
            content,
            "SEARCH\n",
            "b\nc\nNEW\n",
        )
        assert result == "a\nb\nc\nNEW\nd\n"


# ---------------------------------------------------------------------------
# Unit tests: _strip_trailing_overlap / _strip_leading_overlap
# ---------------------------------------------------------------------------

class TestStripTrailingOverlap:
    def test_does_not_strip_single_line_suffix(self) -> None:
        """Single-line overlaps are too likely coincidental to strip."""
        result = _strip_trailing_overlap("new\nreturn 1;\n", "return 1;\nfooter\n")
        assert result == "new\nreturn 1;\n"

    def test_strips_multi_line_suffix(self) -> None:
        """Two or more overlapping lines are stripped."""
        result = _strip_trailing_overlap("new\nreturn 1;\nreturn 2;\n", "return 1;\nreturn 2;\nfooter\n")
        assert result == "new\n"

    def test_returns_unchanged_when_no_overlap(self) -> None:
        result = _strip_trailing_overlap("new\n", "other\n")
        assert result == "new\n"

    def test_returns_unchanged_for_empty_after(self) -> None:
        result = _strip_trailing_overlap("new\n", "")
        assert result == "new\n"

    def test_returns_unchanged_for_empty_replace(self) -> None:
        result = _strip_trailing_overlap("", "after\n")
        assert result == ""

    def test_longest_overlap_wins(self) -> None:
        result = _strip_trailing_overlap("x\na\nb\n", "a\nb\nc\n")
        assert result == "x\n"

    def test_does_not_strip_to_empty(self) -> None:
        """When the entire replace would be stripped, leave it intact."""
        result = _strip_trailing_overlap("a\nb\n", "a\nb\nc\n")
        assert result == "a\nb\n"


class TestStripLeadingOverlap:
    def test_does_not_strip_single_line_prefix(self) -> None:
        """Single-line overlaps are too likely coincidental to strip."""
        result = _strip_leading_overlap("header\nnew\n", "stuff\nheader\n")
        assert result == "header\nnew\n"

    def test_strips_multi_line_prefix(self) -> None:
        """Two or more overlapping lines are stripped."""
        result = _strip_leading_overlap("header1\nheader2\nnew\n", "stuff\nheader1\nheader2\n")
        assert result == "new\n"

    def test_returns_unchanged_when_no_overlap(self) -> None:
        result = _strip_leading_overlap("new\n", "other\n")
        assert result == "new\n"

    def test_returns_unchanged_for_empty_before(self) -> None:
        result = _strip_leading_overlap("new\n", "")
        assert result == "new\n"

    def test_returns_unchanged_for_empty_replace(self) -> None:
        result = _strip_leading_overlap("", "before\n")
        assert result == ""

    def test_longest_overlap_wins(self) -> None:
        result = _strip_leading_overlap("a\nb\nx\n", "z\na\nb\n")
        assert result == "x\n"

    def test_does_not_strip_to_empty(self) -> None:
        """When the entire replace would be stripped, leave it intact."""
        result = _strip_leading_overlap("a\nb\n", "z\na\nb\n")
        assert result == "a\nb\n"


# ---------------------------------------------------------------------------
# Unit tests: edits_to_unified_diff
# ---------------------------------------------------------------------------

class TestEditsToUnifiedDiff:
    def test_produces_valid_unified_diff_headers(self) -> None:
        edits = [{"search": "const re = /abc/;\n", "replace": "const _re = /abc/;\n"}]
        diff = edits_to_unified_diff("src/utils.ts", _UTILS_TS_CONTENT, edits)
        assert diff.startswith("--- a/src/utils.ts")
        assert "+++ b/src/utils.ts" in diff

    def test_diff_contains_expected_removals_and_additions(self) -> None:
        edits = [{"search": "const re = /abc/;\n", "replace": "const _re = /abc/;\n"}]
        diff = edits_to_unified_diff("src/utils.ts", _UTILS_TS_CONTENT, edits)
        assert "-const re = /abc/;" in diff
        assert "+const _re = /abc/;" in diff

    def test_returns_empty_string_when_no_change(self) -> None:
        edits = [{"search": "const re = /abc/;\n", "replace": "const re = /abc/;\n"}]
        diff = edits_to_unified_diff("src/utils.ts", _UTILS_TS_CONTENT, edits)
        assert diff == ""

    def test_multiple_edits_applied_sequentially(self) -> None:
        content = "line1\nline2\nline3\n"
        edits = [
            {"search": "line1\n", "replace": "LINE1\n"},
            {"search": "line3\n", "replace": "LINE3\n"},
        ]
        diff = edits_to_unified_diff("f.ts", content, edits)
        assert "-line1" in diff
        assert "+LINE1" in diff
        assert "-line3" in diff
        assert "+LINE3" in diff

    def test_propagates_search_not_found_error(self) -> None:
        edits = [{"search": "missing text\n", "replace": "x\n"}]
        with pytest.raises(ValueError, match="not found"):
            edits_to_unified_diff("f.ts", "other content\n", edits)


# ---------------------------------------------------------------------------
# Unit tests: _parse_file_from_location
# ---------------------------------------------------------------------------

class TestParseFileFromLocation:
    def test_extracts_file_with_line(self) -> None:
        assert _parse_file_from_location("src/utils.ts:42") == "src/utils.ts"

    def test_returns_location_when_no_colon(self) -> None:
        assert _parse_file_from_location("src/utils.ts") == "src/utils.ts"

    def test_handles_windows_style_path(self) -> None:
        result = _parse_file_from_location("src/deep/file.ts:100")
        assert result == "src/deep/file.ts"


# ---------------------------------------------------------------------------
# Unit tests: _parse_patch_response
# ---------------------------------------------------------------------------

class TestParsePatchResponse:
    def test_parses_valid_response(self) -> None:
        raw = json.dumps({
            "edits": _make_valid_edits(),
            "explanation": "Hoisted regex",
            "estimated_lines_changed": 2,
        })
        result = _parse_patch_response(
            raw, _make_trace(), file_contents={"src/utils.ts": _UTILS_TS_CONTENT}
        )
        assert result is not None
        assert "--- a/src/utils.ts" in result.diff
        assert result.explanation == "Hoisted regex"

    def test_returns_none_for_null_edits(self) -> None:
        raw = json.dumps({"edits": None, "explanation": "Could not fix"})
        result = _parse_patch_response(raw, None)
        assert result is None

    def test_returns_none_for_empty_edits_list(self) -> None:
        raw = json.dumps({"edits": [], "explanation": "no change"})
        result = _parse_patch_response(raw, None)
        assert result is None

    def test_returns_none_for_invalid_json(self) -> None:
        result = _parse_patch_response("not json", None)
        assert result is None

    def test_returns_none_when_search_not_found(self) -> None:
        raw = json.dumps({
            "edits": [{"file": "src/utils.ts", "search": "NONEXISTENT\n", "replace": "x\n"}],
            "explanation": "fix",
            "estimated_lines_changed": 1,
        })
        result = _parse_patch_response(
            raw, None, file_contents={"src/utils.ts": _UTILS_TS_CONTENT}
        )
        assert result is None

    def test_parses_markdown_fenced_json(self) -> None:
        raw = (
            "```json\n"
            + json.dumps({
                "reasoning": "I can fix this safely",
                "edits": _make_valid_edits(),
                "explanation": "Hoisted regex",
                "estimated_lines_changed": 2,
            })
            + "\n```"
        )
        result = _parse_patch_response(
            raw, _make_trace(), file_contents={"src/utils.ts": _UTILS_TS_CONTENT}
        )
        assert result is not None
        assert "--- a/src/utils.ts" in result.diff
        assert result.explanation == "Hoisted regex"

    def test_attaches_thinking_trace(self) -> None:
        trace = _make_trace()
        raw = json.dumps({
            "edits": _make_valid_edits(),
            "explanation": "ok",
        })
        result = _parse_patch_response(
            raw, trace, file_contents={"src/utils.ts": _UTILS_TS_CONTENT}
        )
        assert result is not None
        assert result.thinking_trace is trace

    def test_touched_files_derived_from_edits(self) -> None:
        raw = json.dumps({
            "edits": _make_valid_edits("src/utils.ts"),
            "explanation": "ok",
        })
        result = _parse_patch_response(
            raw, None, file_contents={"src/utils.ts": _UTILS_TS_CONTENT}
        )
        assert result is not None
        assert "src/utils.ts" in result.touched_files


# ---------------------------------------------------------------------------
# Integration tests: generate_agent_patch
# ---------------------------------------------------------------------------

class TestGenerateAgentPatch:
    async def test_returns_patch_for_valid_response(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.ts").write_text(_UTILS_TS_CONTENT)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=_make_response())

        opp = _make_opportunity("src/utils.ts:10")
        result = await generate_agent_patch(opp, tmp_path, mock_provider, _make_config())

        assert result is not None
        assert result.diff != ""
        assert result.thinking_trace is not None

    async def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=_make_response())

        opp = _make_opportunity("nonexistent.ts:1")
        result = await generate_agent_patch(opp, tmp_path, mock_provider, _make_config())
        assert result is None

    async def test_returns_none_when_llm_returns_empty_edits(self, tmp_path: Path) -> None:
        (tmp_path / "a.ts").write_text("code")
        null_response = LLMResponse(
            content=json.dumps({"edits": [], "explanation": "can't fix"}),
            thinking_trace=_make_trace(),
        )

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=null_response)

        opp = _make_opportunity("a.ts:1")
        result = await generate_agent_patch(opp, tmp_path, mock_provider, _make_config())
        assert result is None

    async def test_respects_constraint_max_lines(self, tmp_path: Path) -> None:
        (tmp_path / "big.ts").write_text(_BIG_FILE_CONTENT)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[
            _make_response(_make_big_edits()),
            LLMResponse(
                content=json.dumps({"edits": [], "explanation": None}),
                thinking_trace=_make_trace(),
            ),
        ])

        opp = _make_opportunity("big.ts:1")
        result = await generate_agent_patch(opp, tmp_path, mock_provider, _make_config())
        if result is not None:
            assert result.estimated_lines_changed <= 200

    async def test_approach_override_is_used_instead_of_opportunity_approach(
        self, tmp_path: Path,
    ) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.ts").write_text(_UTILS_TS_CONTENT)

        captured_prompts: list[str] = []

        async def fake_complete(messages, config):
            for m in messages:
                if m.role == "user":
                    captured_prompts.append(m.content)
            return _make_response()

        mock_provider = MagicMock()
        mock_provider.complete = fake_complete

        opp = _make_opportunity("src/utils.ts:10")
        await generate_agent_patch(
            opp, tmp_path, mock_provider, _make_config(),
            approach_override="my custom override approach",
        )

        assert len(captured_prompts) == 1
        assert "my custom override approach" in captured_prompts[0]
        assert "hoist regex" not in captured_prompts[0]


# ---------------------------------------------------------------------------
# Integration tests: generate_agent_patch_with_diagnostics
# ---------------------------------------------------------------------------

class TestGenerateAgentPatchWithDiagnostics:
    async def test_success_returns_patch_and_try_diagnostics(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.ts").write_text(_UTILS_TS_CONTENT)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=_make_response())

        outcome = await generate_agent_patch_with_diagnostics(
            _make_opportunity("src/utils.ts:10"),
            tmp_path,
            mock_provider,
            _make_config(),
        )

        assert outcome.success is True
        assert outcome.patch is not None
        assert outcome.failure_stage is None
        assert len(outcome.tries) == 1
        t = outcome.tries[0]
        assert t.success is True
        assert t.patch is not None
        assert t.patch.diff.startswith("--- a/src/utils.ts")
        assert t.patch_trace is not None

    async def test_json_parse_failure_retries_and_records_two_tries(self, tmp_path: Path) -> None:
        """json_parse is retryable — the loop makes 2 attempts and records both."""
        (tmp_path / "a.ts").write_text("const x = 1;\n")
        bad_response = LLMResponse(content="not json", thinking_trace=_make_trace())

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=bad_response)

        outcome = await generate_agent_patch_with_diagnostics(
            _make_opportunity("a.ts:1"),
            tmp_path,
            mock_provider,
            _make_config(),
        )

        assert outcome.success is False
        assert outcome.patch is None
        assert outcome.failure_stage == "json_parse"
        # Both attempts are recorded (original + one retry)
        assert len(outcome.tries) == 2
        assert outcome.tries[0].failure_stage == "json_parse"
        assert outcome.tries[1].failure_stage == "json_parse"

    async def test_constraint_failure_records_multiple_tries(self, tmp_path: Path) -> None:
        (tmp_path / "big.ts").write_text(_BIG_FILE_CONTENT)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            side_effect=[
                _make_response(_make_big_edits()),
                _make_response(_make_big_edits()),
            ]
        )

        outcome = await generate_agent_patch_with_diagnostics(
            _make_opportunity("big.ts:1"),
            tmp_path,
            mock_provider,
            _make_config(),
        )

        assert outcome.success is False
        assert outcome.patch is None
        assert outcome.failure_stage == "constraint"
        assert len(outcome.tries) == 2
        assert outcome.tries[0].failure_stage == "constraint"
        assert outcome.tries[1].failure_stage == "constraint"

    async def test_null_edits_returns_null_diff_failure_stage(self, tmp_path: Path) -> None:
        (tmp_path / "a.ts").write_text("code\n")
        null_response = LLMResponse(
            content=json.dumps({"edits": None, "explanation": "can't fix"}),
            thinking_trace=_make_trace(),
        )
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=null_response)

        outcome = await generate_agent_patch_with_diagnostics(
            _make_opportunity("a.ts:1"),
            tmp_path,
            mock_provider,
            _make_config(),
        )

        assert outcome.success is False
        assert outcome.patch is None
        assert outcome.failure_stage == "null_diff"
        assert len(outcome.tries) == 1
        assert outcome.tries[0].failure_stage == "null_diff"

    async def test_search_not_found_retries_and_records_two_tries(self, tmp_path: Path) -> None:
        """search_not_found is retryable — both attempts are recorded on repeated failure."""
        (tmp_path / "a.ts").write_text("const x = 1;\n")
        bad_search_response = LLMResponse(
            content=json.dumps({
                "edits": [{"file": "a.ts", "search": "DOES NOT EXIST\n", "replace": "x\n"}],
                "explanation": "fix",
                "estimated_lines_changed": 1,
            }),
            thinking_trace=_make_trace(),
        )
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=bad_search_response)

        outcome = await generate_agent_patch_with_diagnostics(
            _make_opportunity("a.ts:1"),
            tmp_path,
            mock_provider,
            _make_config(),
        )

        assert outcome.success is False
        assert outcome.patch is None
        assert outcome.failure_stage == PATCHGEN_FAILURE_STAGE_SEARCH_NOT_FOUND
        # Both attempts recorded
        assert len(outcome.tries) == 2
        assert outcome.tries[0].failure_stage == PATCHGEN_FAILURE_STAGE_SEARCH_NOT_FOUND
        assert outcome.tries[1].failure_stage == PATCHGEN_FAILURE_STAGE_SEARCH_NOT_FOUND

    async def test_search_not_found_retry_succeeds_on_second_attempt(self, tmp_path: Path) -> None:
        """If the second attempt produces a valid patch, the outcome is success."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.ts").write_text(_UTILS_TS_CONTENT)

        bad_response = LLMResponse(
            content=json.dumps({
                "edits": [{"file": "src/utils.ts", "search": "WRONG TEXT\n", "replace": "x\n"}],
                "explanation": "fix",
                "estimated_lines_changed": 1,
            }),
            thinking_trace=_make_trace(),
        )
        good_response = _make_response()

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[bad_response, good_response])

        outcome = await generate_agent_patch_with_diagnostics(
            _make_opportunity("src/utils.ts:10"),
            tmp_path,
            mock_provider,
            _make_config(),
        )

        assert outcome.success is True
        assert outcome.patch is not None
        assert len(outcome.tries) == 2
        assert outcome.tries[0].failure_stage == PATCHGEN_FAILURE_STAGE_SEARCH_NOT_FOUND
        assert outcome.tries[1].success is True

    async def test_json_parse_retry_succeeds_on_second_attempt(self, tmp_path: Path) -> None:
        """If the second attempt produces valid JSON, the outcome is success."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.ts").write_text(_UTILS_TS_CONTENT)

        bad_response = LLMResponse(content="not valid json at all", thinking_trace=_make_trace())
        good_response = _make_response()

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[bad_response, good_response])

        outcome = await generate_agent_patch_with_diagnostics(
            _make_opportunity("src/utils.ts:10"),
            tmp_path,
            mock_provider,
            _make_config(),
        )

        assert outcome.success is True
        assert outcome.patch is not None
        assert len(outcome.tries) == 2
        assert outcome.tries[0].failure_stage == PATCHGEN_FAILURE_STAGE_JSON_PARSE
        assert outcome.tries[1].success is True

    async def test_retry_prompt_includes_corrective_feedback(self, tmp_path: Path) -> None:
        """The second LLM call receives a prompt augmented with corrective instructions."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.ts").write_text(_UTILS_TS_CONTENT)

        bad_response = LLMResponse(
            content=json.dumps({
                "edits": [{"file": "src/utils.ts", "search": "WRONG\n", "replace": "x\n"}],
                "explanation": "fix",
                "estimated_lines_changed": 1,
            }),
            thinking_trace=_make_trace(),
        )
        good_response = _make_response()

        captured_prompts: list[str] = []

        async def fake_complete(messages, config):
            for m in messages:
                if m.role == "user":
                    captured_prompts.append(m.content)
            return captured_prompts.__len__() == 1 and bad_response or good_response

        async def side_effect(messages, config):
            for m in messages:
                if m.role == "user":
                    captured_prompts.append(m.content)
            if len(captured_prompts) == 1:
                return bad_response
            return good_response

        mock_provider = MagicMock()
        mock_provider.complete = side_effect

        await generate_agent_patch_with_diagnostics(
            _make_opportunity("src/utils.ts:10"),
            tmp_path,
            mock_provider,
            _make_config(),
        )

        assert len(captured_prompts) == 2
        # Retry prompt must contain the corrective signal
        assert "PREVIOUS ATTEMPT FAILED" in captured_prompts[1]
        assert "verbatim" in captured_prompts[1]

    async def test_null_diff_does_not_trigger_retry(self, tmp_path: Path) -> None:
        """null_diff (LLM chose to skip) is NOT retried — it's an intentional response."""
        (tmp_path / "a.ts").write_text("code\n")
        null_response = LLMResponse(
            content=json.dumps({"edits": [], "explanation": "can't fix"}),
            thinking_trace=_make_trace(),
        )
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=null_response)

        outcome = await generate_agent_patch_with_diagnostics(
            _make_opportunity("a.ts:1"),
            tmp_path,
            mock_provider,
            _make_config(),
        )

        assert outcome.success is False
        assert outcome.failure_stage == "null_diff"
        # Only one attempt — null_diff is not retried
        assert len(outcome.tries) == 1
        mock_provider.complete.assert_called_once()


# ---------------------------------------------------------------------------
# Unit tests: _build_correction_feedback
# ---------------------------------------------------------------------------

class TestBuildCorrectionFeedback:
    def test_search_not_found_feedback_contains_key_instructions(self) -> None:
        result = _build_correction_feedback(
            "my approach", PATCHGEN_FAILURE_STAGE_SEARCH_NOT_FOUND, "search block not found"
        )
        assert "my approach" in result
        assert "PREVIOUS ATTEMPT FAILED" in result
        assert "verbatim" in result
        assert "search block not found" in result

    def test_json_parse_feedback_mentions_json(self) -> None:
        result = _build_correction_feedback(
            "my approach", PATCHGEN_FAILURE_STAGE_JSON_PARSE, "Expecting value: line 1"
        )
        assert "my approach" in result
        assert "JSON" in result
        assert "Expecting value: line 1" in result

    def test_unknown_stage_returns_original_approach(self) -> None:
        result = _build_correction_feedback("my approach", "unknown_stage", "some error")
        assert result == "my approach"
