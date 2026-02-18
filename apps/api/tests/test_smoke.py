import pytest

from app.main import create_app


def test_app_creates_successfully():
    """Verify the FastAPI app factory produces a valid app instance."""
    app = create_app()
    assert app is not None
    assert app.title == "Coreloop API"


def test_app_imports():
    """Verify core modules can be imported without errors."""
    from app.core.config import Settings

    settings = Settings()
    assert settings.debug is True


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Verify the health endpoint returns 200 with expected payload."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
