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
    registration_mode: Literal["closed", "invite_only", "approval", "open"] = "invite_only"
    invitation_code_secret: SecretStr = SecretStr("")
    auth_rate_limit_window_seconds: int = 15 * 60
    auth_login_rate_limit: int = 10
    auth_registration_rate_limit: int = 5

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
    character_speech_review_enabled: bool = False

    # Independent from the text-AI provider so an existing DeepSeek key/model
    # remains untouched. This secret is server-only and is never bundled into
    # the browser application.
    literacy_asr_provider: Literal["disabled", "dashscope"] = "disabled"
    literacy_asr_base_url: str = (
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    )
    literacy_asr_api_key: SecretStr = SecretStr("")
    literacy_asr_model: str = "qwen-audio-3.0-asr-flash"
    literacy_asr_timeout_seconds: float = 15.0
    literacy_asr_max_audio_bytes: int = 2 * 1024 * 1024

    # Reading TTS intentionally reuses the already server-only Model Studio
    # credential/base URL.  It never exposes that credential to the browser.
    reading_tts_enabled: bool = True
    reading_tts_model: str = "qwen3-tts-flash"
    reading_tts_voice: str = "Cherry"
    reading_tts_timeout_seconds: float = 30.0

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized origins from the comma-separated environment value."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def literacy_asr_configured(self) -> bool:
        """Return whether the high-accuracy diagnostic ASR path is usable."""
        return bool(
            self.literacy_asr_provider == "dashscope"
            and self.literacy_asr_api_key.get_secret_value().strip()
            and self.literacy_asr_model.strip()
            and self.literacy_asr_base_url.strip()
        )

    @property
    def reading_tts_configured(self) -> bool:
        """Return whether server-side story TTS can use the Model Studio account."""
        return bool(
            self.reading_tts_enabled
            and self.literacy_asr_api_key.get_secret_value().strip()
            and self.literacy_asr_base_url.strip()
            and self.reading_tts_model.strip()
            and self.reading_tts_voice.strip()
        )

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
        invitation_secret = self.invitation_code_secret.get_secret_value()
        if invitation_secret and len(invitation_secret) < 32:
            raise ValueError("INVITATION_CODE_SECRET must contain at least 32 characters")
        if self.auth_rate_limit_window_seconds < 1:
            raise ValueError("AUTH_RATE_LIMIT_WINDOW_SECONDS must be positive")
        if self.auth_login_rate_limit < 1 or self.auth_registration_rate_limit < 1:
            raise ValueError("Authentication rate limits must be positive")
        if self.app_environment == "production" and self.registration_mode not in {
            "closed",
            "invite_only",
        }:
            raise ValueError(
                "Production REGISTRATION_MODE currently supports only closed or invite_only"
            )
        if self.literacy_asr_timeout_seconds <= 0:
            raise ValueError("LITERACY_ASR_TIMEOUT_SECONDS must be positive")
        if self.literacy_asr_max_audio_bytes < 1024:
            raise ValueError("LITERACY_ASR_MAX_AUDIO_BYTES must be at least 1024")
        if self.reading_tts_timeout_seconds <= 0:
            raise ValueError("READING_TTS_TIMEOUT_SECONDS must be positive")
        return self

    @property
    def effective_invitation_code_secret(self) -> str:
        """Use a dedicated invitation HMAC key when supplied, otherwise the auth secret."""
        return self.invitation_code_secret.get_secret_value() or self.auth_secret.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    """Parse environment configuration once per process."""
    return Settings()
