"""Tests for LLM provider implementations.

Uses mocked HTTP calls so no real API keys are needed.
Covers: response parsing, reasoning extraction, error mapping per provider.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runner.llm.provider import LLMProviderError
from runner.llm.types import LLMConfig, LLMMessage, ThinkingTrace


def _make_config(provider: str, model: str) -> LLMConfig:
    return LLMConfig(provider=provider, model=model, api_key="test-key")


def _make_messages() -> list[LLMMessage]:
    return [
        LLMMessage(role="system", content="You are an expert."),
        LLMMessage(role="user", content="Find issues in this code."),
    ]


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class TestOpenAIProvider:
    async def test_complete_returns_llm_response(self) -> None:
        from runner.llm.openai_provider import OpenAIProvider

        mock_usage = MagicMock(prompt_tokens=50, completion_tokens=100)
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "reasoning": "I analysed the code carefully.",
            "opportunities": [],
        })
        mock_choice.message.reasoning_content = None
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock(
            choices=[mock_choice],
            usage=mock_usage,
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        fake_openai = SimpleNamespace(
            AsyncOpenAI=MagicMock(return_value=mock_client),
            AuthenticationError=type("AuthenticationError", (Exception,), {}),
            RateLimitError=type("RateLimitError", (Exception,), {}),
            APIError=type("APIError", (Exception,), {}),
        )

        with patch.dict("sys.modules", {"openai": fake_openai}):
            provider = OpenAIProvider()
            response = await provider.complete(_make_messages(), _make_config("openai", "gpt-4o"))

        assert response.finish_reason == "stop"
        assert response.thinking_trace.prompt_tokens == 50
        assert response.thinking_trace.completion_tokens == 100
        assert response.thinking_trace.provider == "openai"
        assert "analysed" in response.thinking_trace.reasoning

    async def test_reasoning_extracted_from_json(self) -> None:
        from runner.llm.openai_provider import _extract_reasoning

        payload = json.dumps({"reasoning": "deep thoughts", "result": "ok"})
        assert _extract_reasoning(payload) == "deep thoughts"

    def test_extract_reasoning_handles_invalid_json(self) -> None:
        from runner.llm.openai_provider import _extract_reasoning

        assert _extract_reasoning("not json") == ""
        assert _extract_reasoning("") == ""

    async def test_auth_error_raises_provider_error(self) -> None:
        from runner.llm.openai_provider import OpenAIProvider

        authentication_error = type("AuthenticationError", (Exception,), {})
        rate_limit_error = type("RateLimitError", (Exception,), {})
        api_error = type("APIError", (Exception,), {})
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=authentication_error("invalid key")
        )
        fake_openai = SimpleNamespace(
            AsyncOpenAI=MagicMock(return_value=mock_client),
            AuthenticationError=authentication_error,
            RateLimitError=rate_limit_error,
            APIError=api_error,
        )

        with patch.dict("sys.modules", {"openai": fake_openai}):
            provider = OpenAIProvider()
            with pytest.raises(LLMProviderError) as exc_info:
                await provider.complete(_make_messages(), _make_config("openai", "gpt-4o"))

        assert "openai" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

class TestAnthropicProvider:
    async def test_complete_extracts_thinking_block(self) -> None:
        from runner.llm.anthropic_provider import AnthropicProvider

        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        thinking_block.thinking = "Step 1: I looked at the imports..."

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = json.dumps({"opportunities": []})

        mock_usage = MagicMock(input_tokens=80, output_tokens=120)
        mock_response = MagicMock(
            content=[thinking_block, text_block],
            stop_reason="end_turn",
            usage=mock_usage,
        )

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        fake_anthropic = SimpleNamespace(
            AsyncAnthropic=MagicMock(return_value=mock_client)
        )

        with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
            provider = AnthropicProvider()
            cfg = _make_config("anthropic", "claude-haiku-3-5")  # non-thinking model
            cfg.enable_thinking = False
            response = await provider.complete(_make_messages(), cfg)

        assert "Step 1" in response.thinking_trace.reasoning
        assert response.thinking_trace.provider == "anthropic"
        assert response.thinking_trace.prompt_tokens == 80

    async def test_fallback_to_json_reasoning_when_no_thinking_block(self) -> None:
        from runner.llm.anthropic_provider import AnthropicProvider, _extract_reasoning_from_json

        payload = json.dumps({"reasoning": "fallback reasoning"})
        assert _extract_reasoning_from_json(payload) == "fallback reasoning"

    def test_extract_reasoning_handles_empty(self) -> None:
        from runner.llm.anthropic_provider import _extract_reasoning_from_json

        assert _extract_reasoning_from_json("") == ""
        assert _extract_reasoning_from_json("null") == ""


# ---------------------------------------------------------------------------
# Google provider
# ---------------------------------------------------------------------------

class TestGoogleProvider:
    async def test_complete_returns_response(self) -> None:
        from runner.llm.google_provider import GoogleProvider

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "reasoning": "Gemini reasoning here",
            "files": ["src/utils.ts"],
        })
        mock_response.candidates = []
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=40,
            candidates_token_count=60,
        )

        mock_model = MagicMock()
        mock_chat = MagicMock()
        mock_chat.send_message_async = AsyncMock(return_value=mock_response)
        mock_model.start_chat.return_value = mock_chat
        fake_genai = SimpleNamespace(
            configure=MagicMock(),
            GenerationConfig=MagicMock(return_value=MagicMock()),
            GenerativeModel=MagicMock(return_value=mock_model),
        )
        fake_google = SimpleNamespace(generativeai=fake_genai)

        with patch.dict(
            "sys.modules",
            {
                "google": fake_google,
                "google.generativeai": fake_genai,
            },
        ):
            provider = GoogleProvider()
            response = await provider.complete(
                _make_messages(), _make_config("google", "gemini-2.0-flash")
            )

        assert response.thinking_trace.provider == "google"
        assert "Gemini reasoning" in response.thinking_trace.reasoning
        assert response.thinking_trace.prompt_tokens == 40

    def test_extract_reasoning_from_json(self) -> None:
        from runner.llm.google_provider import _extract_reasoning_from_json

        payload = json.dumps({"reasoning": "google thoughts", "result": []})
        assert _extract_reasoning_from_json(payload) == "google thoughts"

    def test_extract_reasoning_handles_missing_field(self) -> None:
        from runner.llm.google_provider import _extract_reasoning_from_json

        payload = json.dumps({"files": ["a.ts"]})
        assert _extract_reasoning_from_json(payload) == ""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_get_provider_anthropic(self) -> None:
        from runner.llm.factory import get_provider
        from runner.llm.anthropic_provider import AnthropicProvider

        p = get_provider("anthropic")
        assert isinstance(p, AnthropicProvider)

    def test_get_provider_openai(self) -> None:
        from runner.llm.factory import get_provider
        from runner.llm.openai_provider import OpenAIProvider

        p = get_provider("openai")
        assert isinstance(p, OpenAIProvider)

    def test_get_provider_google(self) -> None:
        from runner.llm.factory import get_provider
        from runner.llm.google_provider import GoogleProvider

        p = get_provider("google")
        assert isinstance(p, GoogleProvider)

    def test_unknown_provider_raises(self) -> None:
        from runner.llm.factory import get_provider

        with pytest.raises(LLMProviderError):
            get_provider("unknown-provider")

    def test_case_insensitive(self) -> None:
        from runner.llm.factory import get_provider

        p = get_provider("ANTHROPIC")
        assert p is not None
