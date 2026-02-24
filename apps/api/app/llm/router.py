"""LLM configuration endpoints.

Routes:
  GET /llm/models  — list all available models grouped by provider

This is a static catalogue endpoint — no auth required for MVP since
the model list is public information. The runner reads API keys from
environment variables, not from this endpoint.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/llm", tags=["llm"])

# Static registry of supported models per provider.
# Kept here (not in the runner) so the frontend can populate
# the model selector without a runner dependency.
AVAILABLE_MODELS: dict[str, list[dict]] = {
    "anthropic": [
        {
            "id": "claude-sonnet-4-6",
            "label": "Claude Sonnet 4.6",
            "description": "Best reasoning-to-cost ratio (recommended)",
        },
        {
            "id": "claude-opus-4-6",
            "label": "Claude Opus 4.6",
            "description": "Highest capability, highest cost",
        },
        {
            "id": "claude-haiku-4-5",
            "label": "Claude Haiku 4.5",
            "description": "Fastest, lowest cost",
        },
    ],
    "openai": [
        {"id": "gpt-4.1", "label": "GPT-4.1", "description": "Best reasoning-to-cost ratio (recommended)"},
        {"id": "gpt-5.2", "label": "GPT-5.2", "description": "Flagship model, best quality"},
        {"id": "gpt-5-mini", "label": "GPT-5 Mini", "description": "Fast and cost-efficient"},
    ],
    "google": [
        {
            "id": "gemini-2.5-pro",
            "label": "Gemini 2.5 Pro",
            "description": "Highest capability (recommended)",
        },
        {
            "id": "gemini-2.5-flash",
            "label": "Gemini 2.5 Flash",
            "description": "Fast and cost-efficient",
        },
        {
            "id": "gemini-2.5-flash-lite",
            "label": "Gemini 2.5 Flash Lite",
            "description": "Lowest cost",
        },
    ],
}


@router.get("/models")
async def list_models() -> dict:
    """Return all available LLM models grouped by provider.

    Used by the frontend settings panel to populate provider and model
    selector dropdowns.
    """
    return {
        "providers": [
            {
                "id": provider_id,
                "label": provider_id.capitalize(),
                "models": models,
            }
            for provider_id, models in AVAILABLE_MODELS.items()
        ]
    }
