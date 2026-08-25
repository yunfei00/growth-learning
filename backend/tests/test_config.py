"""Configuration behavior tests."""

import pytest

from app.core.config import Settings
from app.integrations.object_storage import (
    ObjectStorageConfigurationError,
    build_minio_client,
)


def test_settings_normalize_cors_origins() -> None:
    settings = Settings(cors_origins="http://localhost:3000, https://app.example.com ")

    assert settings.ai_timeout_seconds == 60.0
    assert settings.registration_mode == "invite_only"
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


def test_production_rejects_placeholder_or_short_auth_secret() -> None:
    with pytest.raises(ValueError, match="AUTH_SECRET"):
        Settings(app_environment="production")
    with pytest.raises(ValueError, match="AUTH_SECRET"):
        Settings(app_environment="production", auth_secret="too-short")


def test_cookie_and_cors_security_combinations_are_validated() -> None:
    with pytest.raises(ValueError, match="SameSite=None"):
        Settings(app_environment="test", auth_cookie_samesite="none", auth_cookie_secure=False)
    with pytest.raises(ValueError, match="Wildcard CORS"):
        Settings(app_environment="test", cors_origins="*")
    with pytest.raises(ValueError, match="INVITATION_CODE_SECRET"):
        Settings(app_environment="test", invitation_code_secret="too-short")
    with pytest.raises(ValueError, match="REGISTRATION_MODE"):
        Settings(
            app_environment="production",
            auth_secret="a-production-auth-secret-with-more-than-32-characters",
            registration_mode="open",
        )
