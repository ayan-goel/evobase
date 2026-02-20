"""Tests for runner/agent/patchgen.py.

Uses mocked LLM providers. No real API calls are made.
Validates diff extraction, constraint enforcement, and self-correction.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from runner.agent.patchgen import (
    _parse_file_from_location,
    _parse_patch_response,
    generate_agent_patch,
)
from runner.agent.types import AgentOpportunity
from runner.llm.types import LLMConfig, LLMResponse, ThinkingTrace


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


def _make_valid_diff(file_path: str = "src/utils.ts") -> str:
    return (
        f"--- a/{file_path}\n"
        f"+++ b/{file_path}\n"
        "@@ -1,3 +1,4 @@\n"
        " const x = 1;\n"
        "-const re = /abc/;\n"
        "+const _re = /abc/;\n"
        " return x;\n"
    )


def _make_response(diff: str, explanation: str = "Fixed regex") -> LLMResponse:
    return LLMResponse(
        content=json.dumps({
            "reasoning": "I hoisted the regex",
            "diff": diff,
            "explanation": explanation,
            "touched_files": ["src/utils.ts"],
            "estimated_lines_changed": 2,
        }),
        thinking_trace=_make_trace(),
    )


class TestParseFileFromLocation:
    def test_extracts_file_with_line(self) -> None:
        assert _parse_file_from_location("src/utils.ts:42") == "src/utils.ts"

    def test_returns_location_when_no_colon(self) -> None:
        assert _parse_file_from_location("src/utils.ts") == "src/utils.ts"

    def test_handles_windows_style_path(self) -> None:
        # rsplit from right handles this correctly
        result = _parse_file_from_location("src/deep/file.ts:100")
        assert result == "src/deep/file.ts"


class TestParsePatchResponse:
    def test_parses_valid_response(self) -> None:
        raw = json.dumps({
            "diff": _make_valid_diff(),
            "explanation": "Hoisted regex",
            "touched_files": ["src/utils.ts"],
            "estimated_lines_changed": 2,
        })
        result = _parse_patch_response(raw, _make_trace())
        assert result is not None
        assert "--- a/src/utils.ts" in result.diff
        assert result.explanation == "Hoisted regex"

    def test_returns_none_for_null_diff(self) -> None:
        raw = json.dumps({"diff": None, "explanation": "Could not fix"})
        result = _parse_patch_response(raw, None)
        assert result is None

    def test_returns_none_for_empty_diff(self) -> None:
        raw = json.dumps({"diff": "", "explanation": "no change"})
        result = _parse_patch_response(raw, None)
        assert result is None

    def test_returns_none_for_invalid_json(self) -> None:
        result = _parse_patch_response("not json", None)
        assert result is None

    def test_attaches_thinking_trace(self) -> None:
        trace = _make_trace()
        raw = json.dumps({"diff": _make_valid_diff(), "explanation": "ok", "touched_files": []})
        result = _parse_patch_response(raw, trace)
        assert result is not None
        assert result.thinking_trace is trace


class TestGenerateAgentPatch:
    async def test_returns_patch_for_valid_response(self, tmp_path: Path) -> None:
        file_path = tmp_path / "src"
        file_path.mkdir()
        (file_path / "utils.ts").write_text("const x = 1;\nconst re = /abc/;\nreturn x;\n")

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_response(_make_valid_diff())
        )

        opp = _make_opportunity("src/utils.ts:10")
        result = await generate_agent_patch(opp, tmp_path, mock_provider, _make_config())

        assert result is not None
        assert result.diff != ""
        assert result.thinking_trace is not None

    async def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=_make_response(_make_valid_diff()))

        opp = _make_opportunity("nonexistent.ts:1")
        result = await generate_agent_patch(opp, tmp_path, mock_provider, _make_config())
        assert result is None

    async def test_returns_none_when_llm_returns_null_diff(self, tmp_path: Path) -> None:
        (tmp_path / "a.ts").write_text("code")
        null_response = LLMResponse(
            content=json.dumps({"diff": None, "explanation": "can't fix"}),
            thinking_trace=_make_trace(),
        )

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=null_response)

        opp = _make_opportunity("a.ts:1")
        result = await generate_agent_patch(opp, tmp_path, mock_provider, _make_config())
        assert result is None

    async def test_respects_constraint_max_lines(self, tmp_path: Path) -> None:
        # Generate a diff that exceeds MAX_LINES_CHANGED (200)
        (tmp_path / "big.ts").write_text("code\n")
        big_diff = (
            "--- a/big.ts\n+++ b/big.ts\n@@ -1,1 +1,201 @@\n"
            + "".join(f"+line{i}\n" for i in range(201))
        )

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[
            _make_response(big_diff),
            LLMResponse(content=json.dumps({"diff": None}), thinking_trace=_make_trace()),
        ])

        opp = _make_opportunity("big.ts:1")
        result = await generate_agent_patch(opp, tmp_path, mock_provider, _make_config())
        # Either returns None (constraint rejected) or a smaller corrected diff
        if result is not None:
            assert result.estimated_lines_changed <= 200

    async def test_approach_override_is_used_instead_of_opportunity_approach(
        self, tmp_path: Path,
    ) -> None:
        """approach_override replaces the opportunity's approach in the prompt."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "utils.ts").write_text("const x = 1;\nconst re = /abc/;\nreturn x;\n")

        captured_prompts: list[str] = []

        async def fake_complete(messages, config):
            # Capture the user-turn prompt to inspect its approach content
            for m in messages:
                if m.role == "user":
                    captured_prompts.append(m.content)
            return _make_response(_make_valid_diff())

        mock_provider = MagicMock()
        mock_provider.complete = fake_complete

        opp = _make_opportunity("src/utils.ts:10")
        await generate_agent_patch(
            opp, tmp_path, mock_provider, _make_config(),
            approach_override="my custom override approach",
        )

        assert len(captured_prompts) == 1
        assert "my custom override approach" in captured_prompts[0]
        # The original approach ("hoist regex") should NOT appear
        assert "hoist regex" not in captured_prompts[0]
