"""Safe default provider used when AI access is not configured."""

from app.integrations.ai.base import (
    AICompletionRequest,
    AICompletionResponse,
    AIProviderError,
)


class DisabledAIProvider:
    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        del request
        raise AIProviderError("AI provider is disabled")
