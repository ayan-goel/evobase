"""LLM provider factory.

Returns the appropriate provider instance given a provider name string.
The factory validates the provider name eagerly so callers get a clear
error at configuration time rather than at call time.
"""

import logging

from runner.llm.provider import LLMProvider, LLMProviderError
from runner.llm.types import AVAILABLE_MODELS

logger = logging.getLogger(__name__)

# Lazy instantiation — providers are cheap to construct
_PROVIDER_MAP: dict[str, type] = {}


def _build_provider_map() -> dict[str, type]:
    """Build the provider map on first access to allow lazy SDK imports."""
    from runner.llm.anthropic_provider import AnthropicProvider
    from runner.llm.google_provider import GoogleProvider
    from runner.llm.openai_provider import OpenAIProvider

    return {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
    }


def get_provider(provider_name: str) -> LLMProvider:
    """Return a provider instance for the given provider name.

    Args:
        provider_name: One of "openai", "anthropic", "google".

    Returns:
        An LLMProvider instance (fresh per call; providers are stateless).

    Raises:
        LLMProviderError: If the provider name is not recognised.
    """
    global _PROVIDER_MAP
    if not _PROVIDER_MAP:
        _PROVIDER_MAP = _build_provider_map()

    provider_cls = _PROVIDER_MAP.get(provider_name.lower())
    if not provider_cls:
        valid = ", ".join(sorted(_PROVIDER_MAP.keys()))
        raise LLMProviderError(
            provider_name,
            f"Unknown provider '{provider_name}'. Valid options: {valid}",
        )

    return provider_cls()


def validate_model(provider: str, model: str) -> None:
    """Raise LLMProviderError if the model is not in the supported list.

    This is a soft validation — unknown models are allowed to pass through
    to support previews and API changes, but a warning is logged.
    """
    known = AVAILABLE_MODELS.get(provider, [])
    if model not in known:
        logger.warning(
            "Model '%s' not in known list for provider '%s'. "
            "Proceeding anyway — API will reject if unsupported.",
            model, provider,
        )
