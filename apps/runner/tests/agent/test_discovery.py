"""Tests for runner/agent/discovery.py.

Uses mocked LLM provider responses. No real API calls are made.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from runner.agent.discovery import (
    MAX_FILES_TO_ANALYSE,
    MAX_OPPORTUNITIES,
    _parse_file_list,
    _parse_opportunities,
    discover_opportunities,
)
from runner.detector.types import DetectionResult
from runner.llm.types import LLMConfig, LLMResponse, ThinkingTrace


def _make_config() -> LLMConfig:
    return LLMConfig(provider="anthropic", model="claude-sonnet-4-5", api_key="test")


def _make_detection(framework: str = "nextjs") -> DetectionResult:
    return DetectionResult(framework=framework, package_manager="npm")


def _make_trace() -> ThinkingTrace:
    return ThinkingTrace(
        model="claude-sonnet-4-5", provider="anthropic",
        reasoning="I analysed this file",
        prompt_tokens=100, completion_tokens=50,
    )


def _make_response(content: dict) -> LLMResponse:
    return LLMResponse(
        content=json.dumps(content),
        thinking_trace=_make_trace(),
    )


class TestParseFileList:
    def test_parses_valid_json(self) -> None:
        raw = json.dumps({"reasoning": "...", "files": ["src/a.ts", "src/b.ts"]})
        result = _parse_file_list(raw)
        assert result == ["src/a.ts", "src/b.ts"]

    def test_returns_empty_on_invalid_json(self) -> None:
        assert _parse_file_list("not json") == []

    def test_returns_empty_on_empty_string(self) -> None:
        assert _parse_file_list("") == []

    def test_returns_empty_when_no_files_key(self) -> None:
        raw = json.dumps({"reasoning": "nothing"})
        assert _parse_file_list(raw) == []

    def test_handles_empty_files_list(self) -> None:
        raw = json.dumps({"files": []})
        assert _parse_file_list(raw) == []

    def test_filters_falsy_paths(self) -> None:
        raw = json.dumps({"files": ["src/a.ts", "", None, "src/b.ts"]})
        result = _parse_file_list(raw)
        assert "" not in result


class TestParseOpportunities:
    def test_parses_valid_opportunities(self) -> None:
        raw = json.dumps({
            "reasoning": "Found 2 issues",
            "opportunities": [
                {
                    "type": "performance",
                    "location": "src/a.ts:10",
                    "rationale": "slow regex",
                    "approach": "hoist regex",
                    "risk_level": "low",
                    "affected_lines": 3,
                }
            ],
        })
        trace = _make_trace()
        result = _parse_opportunities(raw, trace)
        assert len(result) == 1
        assert result[0].type == "performance"
        assert result[0].location == "src/a.ts:10"
        assert result[0].thinking_trace is trace

    def test_returns_empty_on_invalid_json(self) -> None:
        result = _parse_opportunities("bad json", None)
        assert result == []

    def test_skips_opportunities_without_location(self) -> None:
        raw = json.dumps({
            "opportunities": [
                {"type": "perf", "location": "", "rationale": "x", "approach": "y", "risk_level": "low"},
            ]
        })
        result = _parse_opportunities(raw, None)
        assert result == []

    def test_uses_defaults_for_missing_fields(self) -> None:
        raw = json.dumps({
            "opportunities": [
                {"location": "src/x.ts:1"},
            ]
        })
        result = _parse_opportunities(raw, None)
        assert len(result) == 1
        assert result[0].type == "performance"  # default
        assert result[0].risk_level == "medium"  # default

    def test_handles_empty_opportunities_list(self) -> None:
        raw = json.dumps({"reasoning": "nothing", "opportunities": []})
        result = _parse_opportunities(raw, None)
        assert result == []


class TestDiscoverOpportunities:
    async def test_returns_opportunities_from_mock_provider(self, tmp_path: Path) -> None:
        # Create a source file
        (tmp_path / "utils.ts").write_text("const x = 1;\n")

        file_selection_resp = _make_response({"files": ["utils.ts"]})
        analysis_resp = _make_response({
            "reasoning": "Found a perf issue",
            "opportunities": [{
                "type": "performance",
                "location": "utils.ts:1",
                "rationale": "slow",
                "approach": "fix",
                "risk_level": "low",
                "affected_lines": 1,
            }]
        })

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            side_effect=[file_selection_resp, analysis_resp]
        )

        result = await discover_opportunities(
            repo_dir=tmp_path,
            detection=_make_detection(),
            provider=mock_provider,
            config=_make_config(),
        )

        assert len(result) == 1
        assert result[0].type == "performance"
        assert result[0].location == "utils.ts:1"

    async def test_returns_empty_when_no_files_selected(self, tmp_path: Path) -> None:
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_response({"files": []})
        )

        result = await discover_opportunities(
            repo_dir=tmp_path,
            detection=_make_detection(),
            provider=mock_provider,
            config=_make_config(),
        )

        assert result == []

    async def test_skips_missing_files_gracefully(self, tmp_path: Path) -> None:
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            side_effect=[
                _make_response({"files": ["nonexistent.ts"]}),
            ]
        )

        result = await discover_opportunities(
            repo_dir=tmp_path,
            detection=_make_detection(),
            provider=mock_provider,
            config=_make_config(),
        )

        assert result == []

    async def test_deduplicates_by_location(self, tmp_path: Path) -> None:
        (tmp_path / "a.ts").write_text("code")
        (tmp_path / "b.ts").write_text("code")

        dup_opp = {
            "type": "performance",
            "location": "a.ts:1",
            "rationale": "dup",
            "approach": "fix",
            "risk_level": "low",
            "affected_lines": 1,
        }

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[
            _make_response({"files": ["a.ts", "b.ts"]}),
            _make_response({"opportunities": [dup_opp]}),
            _make_response({"opportunities": [dup_opp]}),  # duplicate location
        ])

        result = await discover_opportunities(
            repo_dir=tmp_path,
            detection=_make_detection(),
            provider=mock_provider,
            config=_make_config(),
        )

        assert len(result) == 1  # deduped

    async def test_sorts_by_risk_score_ascending(self, tmp_path: Path) -> None:
        (tmp_path / "a.ts").write_text("code")

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[
            _make_response({"files": ["a.ts"]}),
            _make_response({
                "opportunities": [
                    {"type": "perf", "location": "a.ts:10", "rationale": "r", "approach": "a", "risk_level": "high", "affected_lines": 1},
                    {"type": "perf", "location": "a.ts:5", "rationale": "r", "approach": "a", "risk_level": "low", "affected_lines": 1},
                ]
            }),
        ])

        result = await discover_opportunities(
            repo_dir=tmp_path,
            detection=_make_detection(),
            provider=mock_provider,
            config=_make_config(),
        )

        assert result[0].risk_level == "low"
        assert result[1].risk_level == "high"
