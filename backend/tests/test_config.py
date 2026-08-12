"""Configuration behavior tests."""

import pytest

from app.core.config import Settings
from app.integrations.object_storage import (
    ObjectStorageConfigurationError,
    build_minio_client,
)


def test_settings_normalize_cors_origins() -> None:
    settings = Settings(cors_origins="http://localhost:3000, https://app.example.com ")

    assert settings.cors_origin_list == [
        "http://localhost:3000",
        "https://app.example.com",
    ]


def test_secret_values_are_not_exposed_in_repr() -> None:
    settings = Settings(
        ai_api_key="very-secret",
        minio_secret_key="storage-secret",
        auth_secret="browser-session-secret",
    )

    representation = repr(settings)
    assert "very-secret" not in representation
    assert "storage-secret" not in representation
    assert "browser-session-secret" not in representation


def test_minio_client_requires_credentials() -> None:
    with pytest.raises(ObjectStorageConfigurationError):
        build_minio_client(Settings(minio_access_key="", minio_secret_key=""))
