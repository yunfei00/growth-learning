"""Provider-neutral AI contracts and adapters."""

from app.integrations.ai.base import AIProvider
from app.integrations.ai.factory import build_ai_provider

__all__ = ["AIProvider", "build_ai_provider"]
