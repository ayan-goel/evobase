"""LLM provider abstraction layer.

Public API:
    get_provider(name) -> LLMProvider
    LLMConfig, LLMMessage, LLMResponse, ThinkingTrace
    AVAILABLE_MODELS, DEFAULT_PROVIDER, DEFAULT_MODEL
"""

from runner.llm.factory import get_provider, validate_model
from runner.llm.provider import LLMProvider, LLMProviderError
from runner.llm.types import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    LLMConfig,
    LLMMessage,
    LLMResponse,
    ThinkingTrace,
)

__all__ = [
    "get_provider",
    "validate_model",
    "LLMProvider",
    "LLMProviderError",
    "LLMConfig",
    "LLMMessage",
    "LLMResponse",
    "ThinkingTrace",
    "AVAILABLE_MODELS",
    "DEFAULT_PROVIDER",
    "DEFAULT_MODEL",
]
