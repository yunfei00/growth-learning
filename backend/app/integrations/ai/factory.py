"""AI provider selection from validated application settings."""

from app.core.config import Settings, get_settings
from app.integrations.ai.base import AIProvider
from app.integrations.ai.disabled import DisabledAIProvider
from app.integrations.ai.openai_compatible import OpenAICompatibleProvider


def build_ai_provider(settings: Settings | None = None) -> AIProvider:
    app_settings = settings or get_settings()
    if app_settings.ai_provider == "disabled":
        return DisabledAIProvider()

    return OpenAICompatibleProvider(
        base_url=app_settings.ai_base_url,
        api_key=app_settings.ai_api_key.get_secret_value(),
        model=app_settings.ai_model,
        timeout_seconds=app_settings.ai_timeout_seconds,
    )
