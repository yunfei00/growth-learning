"""Deterministic queued provider used only by tests and local verification."""

from collections import deque

from app.integrations.ai.base import AICompletionRequest, AICompletionResponse, AIProviderError


class FakeAIProvider:
    def __init__(self, responses: list[str]) -> None:
        self._responses = deque(responses)
        self.requests: list[AICompletionRequest] = []

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        self.requests.append(request)
        if not self._responses:
            raise AIProviderError("Fake provider has no queued response")
        return AICompletionResponse(
            text=self._responses.popleft(),
            provider="fake",
            model="deterministic-test-model",
            finish_reason="stop",
            input_tokens=10,
            output_tokens=20,
        )
