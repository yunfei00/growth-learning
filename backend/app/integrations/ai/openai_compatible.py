"""Generic adapter for OpenAI-compatible chat completion APIs."""

import logging
from typing import Any
from urllib.parse import urlsplit

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
        if request.json_response:
            payload["response_format"] = {"type": "json_object"}
            if urlsplit(self._base_url).hostname == "api.deepseek.com" and self._model.startswith(
                "deepseek-v4"
            ):
                # DeepSeek V4 enables thinking by default. For bounded JSON
                # helpers, non-thinking mode avoids spending the entire output
                # budget on reasoning while preserving JSON Output support.
                payload["thinking"] = {"type": "disabled"}
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            if self._client is not None:
                response = await self._client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_seconds,
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
            result = AICompletionResponse(
                text=choice["message"]["content"],
                provider="openai_compatible",
                model=data.get("model", self._model),
                finish_reason=choice.get("finish_reason"),
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
            logging.getLogger(__name__).info(
                "AI completion succeeded",
                extra={
                    "provider": result.provider,
                    "model": result.model,
                    "finish_reason": result.finish_reason,
                },
            )
            return result
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logging.getLogger(__name__).warning(
                "AI completion failed",
                extra={"provider": "openai_compatible", "model": self._model},
                exc_info=True,
            )
            raise AIProviderError("The AI provider returned an invalid response") from exc
