"""Anthropic (Claude) LLM provider implementation.

Supports: claude-sonnet-4-5, claude-haiku-3-5.

Reasoning capture strategy:
  Extended thinking is enabled via the `thinking` parameter (budget_tokens).
  When the API returns `thinking` content blocks, their `thinking` text is
  captured verbatim as the reasoning trace. This gives full visibility into
  Claude's multi-step reasoning before it produces the answer.

  For models that don't support extended thinking, the `reasoning` field
  in the structured JSON response is used as a fallback.

Response format:
  All prompts instruct Claude to return JSON. The text content block is
  parsed as the structured response; thinking blocks are extracted separately.
"""

import json
import logging
from typing import Optional

from runner.llm.provider import LLMProviderError
from runner.llm.types import LLMConfig, LLMMessage, LLMResponse, ThinkingTrace

logger = logging.getLogger(__name__)

# Extended thinking budget in tokens — covers complex multi-file analysis
_THINKING_BUDGET_TOKENS = 8000

# Models that support extended thinking
_THINKING_MODELS = {"claude-sonnet-4-5", "claude-opus-4-5", "claude-opus-4"}


class AnthropicProvider:
    """Anthropic Messages API provider.

    Uses the anthropic Python SDK. Lazy-imports to avoid errors when
    the SDK is not installed.
    """

    async def complete(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> LLMResponse:
        """Call the Anthropic Messages API with optional extended thinking."""
        try:
            import anthropic
        except ImportError as exc:
            raise LLMProviderError(
                "anthropic",
                "anthropic package not installed. Run: uv add anthropic",
                cause=exc,
            )

        client = anthropic.AsyncAnthropic(api_key=config.api_key)

        # Separate system message from user/assistant turns
        system_content = ""
        api_messages = []
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        use_thinking = (
            config.enable_thinking
            and config.model in _THINKING_MODELS
        )

        kwargs: dict = {
            "model": config.model,
            "max_tokens": config.max_tokens + (_THINKING_BUDGET_TOKENS if use_thinking else 0),
            "messages": api_messages,
        }
        if system_content:
            kwargs["system"] = system_content

        if use_thinking:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": _THINKING_BUDGET_TOKENS,
            }
            # Temperature must be 1 when extended thinking is enabled
            kwargs["temperature"] = 1
        else:
            kwargs["temperature"] = config.temperature

        try:
            response = await client.messages.create(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise LLMProviderError("anthropic", f"Auth failed: {exc}", cause=exc)
        except anthropic.RateLimitError as exc:
            raise LLMProviderError("anthropic", f"Rate limit: {exc}", cause=exc)
        except anthropic.APIError as exc:
            raise LLMProviderError("anthropic", f"API error: {exc}", cause=exc)

        # Extract content blocks
        raw_content = ""
        reasoning_text = ""

        for block in response.content:
            if block.type == "thinking":
                reasoning_text = block.thinking
            elif block.type == "text":
                raw_content = block.text

        # Fallback: extract reasoning from JSON if no thinking block
        if not reasoning_text:
            reasoning_text = _extract_reasoning_from_json(raw_content)

        usage = response.usage
        trace = ThinkingTrace(
            model=config.model,
            provider="anthropic",
            reasoning=reasoning_text,
            prompt_tokens=usage.input_tokens if usage else 0,
            completion_tokens=usage.output_tokens if usage else 0,
        )

        finish_reason = "stop" if response.stop_reason == "end_turn" else response.stop_reason

        return LLMResponse(
            content=raw_content,
            thinking_trace=trace,
            finish_reason=finish_reason,
        )


def _extract_reasoning_from_json(raw_content: str) -> str:
    """Fallback: extract `reasoning` field from JSON response body."""
    if not raw_content:
        return ""
    try:
        data = json.loads(raw_content)
        return str(data.get("reasoning", ""))
    except (json.JSONDecodeError, AttributeError):
        return ""
