"""Google (Gemini) LLM provider implementation.

Supports: gemini-2.0-flash, gemini-1.5-pro.

Reasoning capture strategy:
  Gemini models are instructed via the system prompt to include a `reasoning`
  field in all JSON responses. This field is extracted as the thinking trace.

  When the response contains `candidates[0].content.parts` with separate
  thought parts (available in some Gemini thinking models), those are used
  preferentially.

Response format:
  All prompts instruct the model to return JSON. The `response_mime_type`
  is set to `application/json` to enforce structured output.
"""

import json
import logging

from runner.llm.provider import LLMProviderError
from runner.llm.types import LLMConfig, LLMMessage, LLMResponse, ThinkingTrace

logger = logging.getLogger(__name__)


class GoogleProvider:
    """Google Generative AI (Gemini) provider.

    Uses the google-generativeai Python SDK. Lazy-imports to avoid errors
    when the SDK is not installed.
    """

    async def complete(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> LLMResponse:
        """Call the Gemini API with JSON output mode."""
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise LLMProviderError(
                "google",
                "google-generativeai package not installed. Run: uv add google-generativeai",
                cause=exc,
            )

        genai.configure(api_key=config.api_key)

        # Extract system instruction and build conversation
        system_instruction = ""
        history = []
        last_user_content = ""

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                last_user_content = msg.content
                history.append({"role": "user", "parts": [msg.content]})
            elif msg.role == "assistant":
                history.append({"role": "model", "parts": [msg.content]})

        generation_config = genai.GenerationConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_tokens,
            response_mime_type="application/json",
        )

        model_kwargs: dict = {
            "model_name": config.model,
            "generation_config": generation_config,
        }
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction

        model = genai.GenerativeModel(**model_kwargs)

        try:
            # Use chat for multi-turn; send last user message
            chat_history = history[:-1] if len(history) > 1 else []
            chat = model.start_chat(history=chat_history)
            response = await chat.send_message_async(last_user_content or history[-1]["parts"][0])
        except Exception as exc:
            # Catch-all since google SDK has varied exception types
            error_str = str(exc).lower()
            if "api_key" in error_str or "permission" in error_str:
                raise LLMProviderError("google", f"Auth failed: {exc}", cause=exc)
            if "quota" in error_str or "rate" in error_str:
                raise LLMProviderError("google", f"Rate limit: {exc}", cause=exc)
            raise LLMProviderError("google", f"API error: {exc}", cause=exc)

        raw_content = response.text or ""

        # Try to extract thought parts (available in some Gemini thinking models)
        reasoning_text = _extract_thought_parts(response)
        if not reasoning_text:
            reasoning_text = _extract_reasoning_from_json(raw_content)

        # Token usage from usage_metadata if available
        prompt_tokens = 0
        completion_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            prompt_tokens = getattr(meta, "prompt_token_count", 0) or 0
            completion_tokens = getattr(meta, "candidates_token_count", 0) or 0

        trace = ThinkingTrace(
            model=config.model,
            provider="google",
            reasoning=reasoning_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        return LLMResponse(
            content=raw_content,
            thinking_trace=trace,
            finish_reason="stop",
        )


def _extract_thought_parts(response) -> str:
    """Extract thought content parts from Gemini thinking model responses."""
    try:
        parts = response.candidates[0].content.parts
        thought_texts = [
            p.text for p in parts
            if getattr(p, "thought", False) and p.text
        ]
        return "\n".join(thought_texts)
    except (AttributeError, IndexError):
        return ""


def _extract_reasoning_from_json(raw_content: str) -> str:
    """Extract `reasoning` field from JSON response body."""
    if not raw_content:
        return ""
    try:
        data = json.loads(raw_content)
        return str(data.get("reasoning", ""))
    except (json.JSONDecodeError, AttributeError):
        return ""
