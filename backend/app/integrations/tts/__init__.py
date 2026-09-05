"""Server-side text-to-speech integrations for assisted reading."""

from app.integrations.tts.dashscope import DashScopeTTSProvider, TTSProviderError, TTSSynthesis

__all__ = ["DashScopeTTSProvider", "TTSProviderError", "TTSSynthesis"]
