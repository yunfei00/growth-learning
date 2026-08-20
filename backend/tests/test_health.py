"""HTTP smoke tests."""

import httpx
import pytest

from app.core.config import Settings
from app.main import create_app


@pytest.mark.anyio
async def test_health_endpoint() -> None:
    transport = httpx.ASGITransport(app=create_app(Settings(app_environment="test")))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.0.0", "revision": "unknown"}


@pytest.mark.anyio
async def test_health_exposes_safe_short_revision() -> None:
    settings = Settings(
        app_environment="test",
        app_revision="0123456789abcdef0123456789abcdef01234567",
    )
    transport = httpx.ASGITransport(app=create_app(settings))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.json()["revision"] == "0123456789ab"


@pytest.mark.anyio
async def test_api_v1_foundation() -> None:
    transport = httpx.ASGITransport(app=create_app(Settings(app_environment="test")))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1")

    assert response.status_code == 200
    assert response.json() == {"name": "Growth Learning API", "version": "v1"}


@pytest.mark.anyio
async def test_openapi_uses_configured_proxy_root_path() -> None:
    settings = Settings(app_environment="test", root_path="/growth/api")
    transport = httpx.ASGITransport(app=create_app(settings), root_path="/growth/api")
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["servers"] == [{"url": "/growth/api"}]
