"""OpenAI LLM provider implementation.

Supports: gpt-4o, gpt-4o-mini, o3-mini.

Reasoning capture strategy:
  GPT-4o / gpt-4o-mini — the system prompt instructs the model to include
  a top-level `"reasoning"` field in all JSON responses. This field is
  extracted as the thinking trace.

  o3-mini — uses the native `reasoning_effort` parameter which produces
  reasoning tokens. The reasoning content is captured from the response
  if available, otherwise the structured `"reasoning"` field is used.

All responses are expected in JSON format. The caller's prompt must
request JSON output explicitly (enforced by the prompt layer).
"""

import json
import logging
from typing import Optional

from runner.llm.provider import LLMProviderError
from runner.llm.types import LLMConfig, LLMMessage, LLMResponse, ThinkingTrace

logger = logging.getLogger(__name__)

# Models that support the reasoning_effort parameter
_REASONING_MODELS = {"o3-mini", "o1", "o1-mini", "o3"}


class OpenAIProvider:
    """OpenAI chat completions provider.

    Uses the openai Python SDK (>=1.0). Lazy-imports to avoid import
    errors when the SDK is not installed (other providers still work).
    """

    async def complete(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> LLMResponse:
        """Call the OpenAI chat completions API."""
        try:
            import openai
        except ImportError as exc:
            raise LLMProviderError(
                "openai",
                "openai package not installed. Run: uv add openai",
                cause=exc,
            )

        client = openai.AsyncOpenAI(api_key=config.api_key)

        api_messages = [
            {"role": m.role, "content": m.content} for m in messages
        ]

        kwargs: dict = {
            "model": config.model,
            "messages": api_messages,
            "max_tokens": config.max_tokens,
            "response_format": {"type": "json_object"},
        }

        # o3-mini uses reasoning_effort instead of temperature
        if config.model in _REASONING_MODELS:
            kwargs["reasoning_effort"] = "high"
        else:
            kwargs["temperature"] = config.temperature

        try:
            response = await client.chat.completions.create(**kwargs)
        except openai.AuthenticationError as exc:
            raise LLMProviderError("openai", f"Auth failed: {exc}", cause=exc)
        except openai.RateLimitError as exc:
            raise LLMProviderError("openai", f"Rate limit: {exc}", cause=exc)
        except openai.APIError as exc:
            raise LLMProviderError("openai", f"API error: {exc}", cause=exc)

        choice = response.choices[0]
        raw_content = choice.message.content or ""
        finish_reason = choice.finish_reason or "stop"

        # Extract reasoning from the structured JSON field
        reasoning = _extract_reasoning(raw_content)

        # For reasoning models, prefer the native reasoning_content if present
        if hasattr(choice.message, "reasoning_content") and choice.message.reasoning_content:
            reasoning = choice.message.reasoning_content

        usage = response.usage
        trace = ThinkingTrace(
            model=config.model,
            provider="openai",
            reasoning=reasoning,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

        return LLMResponse(
            content=raw_content,
            thinking_trace=trace,
            finish_reason=finish_reason,
        )


def _extract_reasoning(raw_content: str) -> str:
    """Extract the `reasoning` field from a JSON response string.

    Returns an empty string if the field is absent or the content
    is not valid JSON.
    """
    if not raw_content:
        return ""
    try:
        data = json.loads(raw_content)
        return str(data.get("reasoning", ""))
    except (json.JSONDecodeError, AttributeError):
        return ""
