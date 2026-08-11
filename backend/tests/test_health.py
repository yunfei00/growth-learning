"""HTTP smoke tests."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_endpoint() -> None:
    with TestClient(create_app(Settings(app_environment="test"))) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_v1_foundation() -> None:
    with TestClient(create_app(Settings(app_environment="test"))) as client:
        response = client.get("/api/v1")

    assert response.status_code == 200
    assert response.json() == {"name": "Growth Learning API", "version": "v1"}
