"""Tests for GET /llm/models endpoint."""

import pytest
from httpx import AsyncClient


class TestListModels:
    async def test_returns_200(self, client: AsyncClient) -> None:
        res = await client.get("/llm/models")
        assert res.status_code == 200

    async def test_response_has_providers_key(self, client: AsyncClient) -> None:
        res = await client.get("/llm/models")
        data = res.json()
        assert "providers" in data

    async def test_all_three_providers_present(self, client: AsyncClient) -> None:
        res = await client.get("/llm/models")
        providers = {p["id"] for p in res.json()["providers"]}
        assert "openai" in providers
        assert "anthropic" in providers
        assert "google" in providers

    async def test_each_provider_has_models(self, client: AsyncClient) -> None:
        res = await client.get("/llm/models")
        for provider in res.json()["providers"]:
            assert len(provider["models"]) > 0

    async def test_each_model_has_required_fields(self, client: AsyncClient) -> None:
        res = await client.get("/llm/models")
        for provider in res.json()["providers"]:
            for model in provider["models"]:
                assert "id" in model
                assert "label" in model
                assert "description" in model

    async def test_anthropic_has_claude_sonnet(self, client: AsyncClient) -> None:
        res = await client.get("/llm/models")
        anthropic = next(p for p in res.json()["providers"] if p["id"] == "anthropic")
        model_ids = [m["id"] for m in anthropic["models"]]
        assert "claude-sonnet-4-6" in model_ids

    async def test_openai_has_gpt41_and_gpt5(self, client: AsyncClient) -> None:
        res = await client.get("/llm/models")
        openai = next(p for p in res.json()["providers"] if p["id"] == "openai")
        model_ids = [m["id"] for m in openai["models"]]
        assert "gpt-4.1" in model_ids
        assert "gpt-5.2" in model_ids

    async def test_google_has_gemini_25(self, client: AsyncClient) -> None:
        res = await client.get("/llm/models")
        google = next(p for p in res.json()["providers"] if p["id"] == "google")
        model_ids = [m["id"] for m in google["models"]]
        assert "gemini-2.5-pro" in model_ids
