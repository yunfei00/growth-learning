"""Provider-neutral AI adapter tests that never call an external model."""

import httpx
import pytest

from app.integrations.ai.base import AICompletionRequest, AIMessage, AIProviderError
from app.integrations.ai.disabled import DisabledAIProvider
from app.integrations.ai.openai_compatible import OpenAICompatibleProvider


@pytest.mark.anyio
async def test_disabled_provider_fails_closed() -> None:
    request = AICompletionRequest(messages=[AIMessage(role="user", content="hello")])

    with pytest.raises(AIProviderError, match="disabled"):
        await DisabledAIProvider().complete(request)


@pytest.mark.anyio
async def test_openai_compatible_provider_normalizes_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        assert b'"response_format":{"type":"json_object"}' in request.content
        assert request.url.path == "/v1/chat/completions"
        assert request.extensions["timeout"]["read"] == 7.0
        return httpx.Response(
            200,
            json={
                "model": "provider-model",
                "choices": [{"message": {"content": "A safe story."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 3},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://provider.example/v1",
            api_key="test-key",
            model="configured-model",
            timeout_seconds=7,
            client=client,
        )
        result = await provider.complete(
            AICompletionRequest(
                messages=[AIMessage(role="user", content="Write a story")], json_response=True
            )
        )

    assert result.text == "A safe story."
    assert result.provider == "openai_compatible"
    assert result.model == "provider-model"
    assert result.input_tokens == 4
    assert result.output_tokens == 3
