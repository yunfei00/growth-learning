"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Validated configuration shared by application adapters."""

    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Growth Learning API"
    app_version: str = "1.0.0"
    app_revision: str = "unknown"
    app_environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    root_path: str = ""
    cors_origins: str = "http://localhost:3000"

    auth_secret: SecretStr = SecretStr("development-only-auth-secret-change-before-production")
    auth_cookie_name: str = "growth_learning_session"
    auth_cookie_path: str = "/"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    auth_token_ttl_seconds: int = 60 * 60 * 24 * 7
    auth_token_issuer: str = "growth-learning"

    database_url: str = "postgresql+asyncpg://localhost/growth_learning"
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: SecretStr = SecretStr("")
    minio_secret_key: SecretStr = SecretStr("")
    minio_bucket: str = "growth-learning"
    minio_secure: bool = False
    science_image_max_bytes: int = 10 * 1024 * 1024
    science_video_max_bytes: int = 50 * 1024 * 1024
    science_audio_max_bytes: int = 20 * 1024 * 1024
    export_download_ttl_seconds: int = 60 * 60

    ai_provider: Literal["disabled", "openai_compatible"] = "disabled"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: SecretStr = SecretStr("")
    ai_model: str = ""
    ai_timeout_seconds: float = 60.0
    ai_story_max_attempts: int = 3

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized origins from the comma-separated environment value."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        """Reject known unsafe production authentication and CORS combinations."""
        secret = self.auth_secret.get_secret_value()
        unsafe_secrets = {
            "development-only-auth-secret-change-before-production",
            "local-only-auth-secret-change-me-please",
        }
        if self.app_environment == "production" and (secret in unsafe_secrets or len(secret) < 32):
            raise ValueError("Production AUTH_SECRET must be unique and at least 32 characters")
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            raise ValueError("SameSite=None requires a Secure authentication cookie")
        if "*" in self.cors_origin_list:
            raise ValueError("Wildcard CORS is not allowed with credentialed browser sessions")
        return self


@lru_cache
def get_settings() -> Settings:
    """Parse environment configuration once per process."""
    return Settings()
