"""Generic adapter for OpenAI-compatible chat completion APIs."""

from typing import Any

import httpx

from app.integrations.ai.base import (
    AICompletionRequest,
    AICompletionResponse,
    AIProviderError,
)


class OpenAICompatibleProvider:
    """Support OpenAI, DeepSeek, Qwen/DashScope, or a local compatible API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key or not model:
            raise ValueError("An API key and model are required for an enabled AI provider")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        payload = {
            "model": self._model,
            "messages": [message.model_dump() for message in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            if self._client is not None:
                response = await self._client.post(
                    f"{self._base_url}/chat/completions", headers=headers, json=payload
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions", headers=headers, json=payload
                    )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})
            return AICompletionResponse(
                text=choice["message"]["content"],
                provider="openai_compatible",
                model=data.get("model", self._model),
                finish_reason=choice.get("finish_reason"),
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIProviderError("The AI provider returned an invalid response") from exc
