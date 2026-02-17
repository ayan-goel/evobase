"""Tests for runner/llm/types.py.

Covers: LLMConfig, LLMMessage, ThinkingTrace, LLMResponse, AVAILABLE_MODELS.
"""

import pytest
from runner.llm.types import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    LLMConfig,
    LLMMessage,
    LLMResponse,
    ThinkingTrace,
)


class TestLLMConfig:
    def test_required_fields(self) -> None:
        cfg = LLMConfig(provider="anthropic", model="claude-sonnet-4-5", api_key="sk-test")
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-sonnet-4-5"
        assert cfg.api_key == "sk-test"

    def test_defaults(self) -> None:
        cfg = LLMConfig(provider="openai", model="gpt-4o", api_key="")
        assert cfg.max_tokens == 4096
        assert cfg.temperature == 0.2
        assert cfg.enable_thinking is True

    def test_custom_values(self) -> None:
        cfg = LLMConfig(
            provider="google",
            model="gemini-2.0-flash",
            api_key="key",
            max_tokens=2000,
            temperature=0.0,
            enable_thinking=False,
        )
        assert cfg.max_tokens == 2000
        assert cfg.temperature == 0.0
        assert cfg.enable_thinking is False


class TestLLMMessage:
    def test_user_message(self) -> None:
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_system_message(self) -> None:
        msg = LLMMessage(role="system", content="You are an expert")
        assert msg.role == "system"

    def test_assistant_message(self) -> None:
        msg = LLMMessage(role="assistant", content='{"result": "ok"}')
        assert msg.role == "assistant"


class TestThinkingTrace:
    def test_to_dict_has_required_keys(self) -> None:
        trace = ThinkingTrace(
            model="claude-sonnet-4-5",
            provider="anthropic",
            reasoning="Let me think...",
            prompt_tokens=100,
            completion_tokens=200,
        )
        d = trace.to_dict()
        assert d["model"] == "claude-sonnet-4-5"
        assert d["provider"] == "anthropic"
        assert d["reasoning"] == "Let me think..."
        assert d["prompt_tokens"] == 100
        assert d["completion_tokens"] == 200
        assert d["tokens_used"] == 300

    def test_to_dict_includes_timestamp(self) -> None:
        trace = ThinkingTrace(
            model="gpt-4o", provider="openai", reasoning="",
            prompt_tokens=10, completion_tokens=20,
        )
        assert "timestamp" in trace.to_dict()

    def test_timestamp_is_set_automatically(self) -> None:
        trace = ThinkingTrace(
            model="gemini-2.0-flash", provider="google", reasoning="",
            prompt_tokens=0, completion_tokens=0,
        )
        assert trace.timestamp != ""


class TestLLMResponse:
    def test_is_complete_on_stop(self) -> None:
        trace = ThinkingTrace(model="m", provider="p", reasoning="", prompt_tokens=0, completion_tokens=0)
        resp = LLMResponse(content="{}", thinking_trace=trace, finish_reason="stop")
        assert resp.is_complete() is True

    def test_not_complete_on_length(self) -> None:
        trace = ThinkingTrace(model="m", provider="p", reasoning="", prompt_tokens=0, completion_tokens=0)
        resp = LLMResponse(content="{}", thinking_trace=trace, finish_reason="length")
        assert resp.is_complete() is False

    def test_default_finish_reason_is_stop(self) -> None:
        trace = ThinkingTrace(model="m", provider="p", reasoning="", prompt_tokens=0, completion_tokens=0)
        resp = LLMResponse(content="{}", thinking_trace=trace)
        assert resp.finish_reason == "stop"


class TestAvailableModels:
    def test_all_providers_present(self) -> None:
        assert "openai" in AVAILABLE_MODELS
        assert "anthropic" in AVAILABLE_MODELS
        assert "google" in AVAILABLE_MODELS

    def test_each_provider_has_models(self) -> None:
        for provider, models in AVAILABLE_MODELS.items():
            assert len(models) > 0, f"Provider {provider} has no models"

    def test_default_provider_in_registry(self) -> None:
        assert DEFAULT_PROVIDER in AVAILABLE_MODELS

    def test_default_model_in_registry(self) -> None:
        assert DEFAULT_MODEL in AVAILABLE_MODELS[DEFAULT_PROVIDER]
