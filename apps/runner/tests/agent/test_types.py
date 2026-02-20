"""Tests for runner/agent/types.py."""

import pytest
from runner.agent.types import AgentOpportunity, AgentPatch, AgentRun
from runner.llm.types import ThinkingTrace


def _make_trace() -> ThinkingTrace:
    return ThinkingTrace(
        model="claude-sonnet-4-5", provider="anthropic",
        reasoning="I found an issue", prompt_tokens=10, completion_tokens=20,
    )


class TestAgentOpportunity:
    def test_risk_score_low(self) -> None:
        opp = AgentOpportunity(
            type="performance", location="src/a.ts:5",
            rationale="slow", risk_level="low",
            approaches=["fix"],
        )
        assert opp.risk_score == 0.2

    def test_risk_score_medium(self) -> None:
        opp = AgentOpportunity(
            type="tech_debt", location="src/b.ts:10",
            rationale="messy", risk_level="medium",
            approaches=["clean"],
        )
        assert opp.risk_score == 0.5

    def test_risk_score_high(self) -> None:
        opp = AgentOpportunity(
            type="error_handling", location="src/c.ts:1",
            rationale="crash risk", risk_level="high",
            approaches=["guard"],
        )
        assert opp.risk_score == 0.8

    def test_risk_score_unknown_defaults_to_medium(self) -> None:
        opp = AgentOpportunity(
            type="other", location="src/d.ts:1",
            rationale="x", risk_level="unknown",
            approaches=["y"],
        )
        assert opp.risk_score == 0.5

    def test_approach_property_returns_first_entry(self) -> None:
        opp = AgentOpportunity(
            type="performance", location="src/a.ts:5",
            rationale="slow", risk_level="low",
            approaches=["first approach", "second approach"],
        )
        assert opp.approach == "first approach"

    def test_approach_property_returns_empty_when_no_approaches(self) -> None:
        opp = AgentOpportunity(
            type="performance", location="src/a.ts:5",
            rationale="slow", risk_level="low",
        )
        assert opp.approach == ""

    def test_to_dict_has_all_keys(self) -> None:
        opp = AgentOpportunity(
            type="performance", location="src/a.ts:5",
            rationale="slow", risk_level="low",
            approaches=["fix"],
            thinking_trace=_make_trace(),
        )
        d = opp.to_dict()
        assert "type" in d
        assert "location" in d
        assert "rationale" in d
        assert "approaches" in d
        assert "risk_level" in d
        assert "risk_score" in d
        assert "thinking_trace" in d
        assert d["thinking_trace"] is not None

    def test_to_dict_without_trace(self) -> None:
        opp = AgentOpportunity(
            type="performance", location="src/a.ts:5",
            rationale="slow", risk_level="low",
            approaches=["fix"],
        )
        d = opp.to_dict()
        assert d["thinking_trace"] is None

    def test_to_dict_approaches_list(self) -> None:
        opp = AgentOpportunity(
            type="performance", location="src/a.ts:5",
            rationale="slow", risk_level="low",
            approaches=["strategy A", "strategy B"],
        )
        d = opp.to_dict()
        assert d["approaches"] == ["strategy A", "strategy B"]


class TestAgentPatch:
    def test_to_dict_has_all_keys(self) -> None:
        patch = AgentPatch(
            diff="--- a/f.ts\n+++ b/f.ts\n",
            explanation="Hoisted regex",
            touched_files=["src/f.ts"],
            estimated_lines_changed=5,
            thinking_trace=_make_trace(),
        )
        d = patch.to_dict()
        assert "diff" in d
        assert "explanation" in d
        assert "touched_files" in d
        assert "estimated_lines_changed" in d
        assert "thinking_trace" in d
        assert d["thinking_trace"] is not None

    def test_to_dict_without_trace(self) -> None:
        patch = AgentPatch(diff="diff", explanation="ok", touched_files=[])
        d = patch.to_dict()
        assert d["thinking_trace"] is None


class TestAgentRun:
    def test_successful_patch_count(self) -> None:
        run = AgentRun(
            patches=[
                AgentPatch(diff="d1", explanation="e1", touched_files=[]),
                None,
                AgentPatch(diff="d2", explanation="e2", touched_files=[]),
            ]
        )
        assert run.successful_patch_count == 2

    def test_successful_patch_count_all_none(self) -> None:
        run = AgentRun(patches=[None, None])
        assert run.successful_patch_count == 0

    def test_empty_run(self) -> None:
        run = AgentRun()
        assert run.successful_patch_count == 0
        assert len(run.opportunities) == 0
