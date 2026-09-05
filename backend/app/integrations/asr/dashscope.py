"""Privacy-minimal DashScope ASR adapter for short child utterances.

The adapter accepts audio bytes in memory, sends one Base64 Data URI to the
configured Alibaba Cloud Model Studio endpoint, and returns only transcript and
minimal request metadata. It never writes audio or Base64 payloads to storage.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass

import httpx

DEFAULT_DASHSCOPE_ASR_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
)

_AUDIO_FORMATS = {
    "audio/aac": "aac",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/opus": "opus",
    "audio/wav": "wav",
    "audio/webm": "webm",
    "audio/x-wav": "wav",
}


class ASRProviderError(RuntimeError):
    """Base error for an upstream ASR failure that is not child evidence."""


class ASRConfigurationError(ASRProviderError):
    """The configured provider cannot authenticate or is not enabled correctly."""


class ASRTransportError(ASRProviderError):
    """The provider could not be reached or timed out."""


class ASRNoSpeechError(ASRProviderError):
    """The provider returned no usable transcript for this recording."""


@dataclass(frozen=True)
class ASRTranscription:
    transcript: str
    provider: str
    model: str
    request_id: str | None
    usage_duration_seconds: float | None
    latency_ms: int


def normalize_audio_content_type(content_type: str | None) -> tuple[str, str]:
    """Return a safe MIME type and DashScope format for a browser recording."""

    normalized = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    audio_format = _AUDIO_FORMATS.get(normalized)
    if audio_format is None:
        raise ValueError("Unsupported diagnostic audio format")
    return normalized, audio_format


class DashScopeASRProvider:
    """Synchronous short-file transcription over the DashScope HTTP API."""

    provider_name = "dashscope_qwen_audio_asr"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "qwen-audio-3.0-asr-flash",
        base_url: str = DEFAULT_DASHSCOPE_ASR_URL,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.strip()
        self.timeout_seconds = timeout_seconds
        if not self.api_key or not self.model or not self.base_url:
            raise ASRConfigurationError("Server ASR is not configured")

    async def transcribe(self, audio_bytes: bytes, content_type: str | None) -> ASRTranscription:
        if not audio_bytes:
            raise ASRNoSpeechError("No audio was captured")
        mime_type, audio_format = normalize_audio_content_type(content_type)
        encoded = base64.b64encode(audio_bytes).decode("ascii")
        data_uri = f"data:{mime_type};base64,{encoded}"

        # A literacy diagnostic must not leak the target character, expected
        # pinyin, or accepted readings into prompt/context/hotwords. Only the
        # language hint is sent so the ASR cannot be biased toward the answer.
        payload = {
            "model": self.model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {"data": data_uri},
                            }
                        ],
                    }
                ]
            },
            "parameters": {
                "format": audio_format,
                "language_hints": ["zh"],
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-SSE": "disable",
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.base_url, headers=headers, json=payload)
        except httpx.TimeoutException as error:
            raise ASRTransportError("Server ASR timed out") from error
        except httpx.RequestError as error:
            raise ASRTransportError("Server ASR could not be reached") from error
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))

        if response.status_code in {401, 403}:
            raise ASRConfigurationError("Server ASR authentication failed")
        if response.status_code >= 400:
            raise ASRProviderError(f"Server ASR returned HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as error:
            raise ASRProviderError("Server ASR returned an invalid response") from error

        output = body.get("output") if isinstance(body, dict) else None
        transcript = ""
        if isinstance(output, dict):
            value = output.get("text")
            if isinstance(value, str):
                transcript = value.strip()
            if not transcript:
                sentence = output.get("sentence")
                if isinstance(sentence, dict) and isinstance(sentence.get("text"), str):
                    transcript = sentence["text"].strip()
        if not transcript:
            raise ASRNoSpeechError("Server ASR did not return speech text")

        usage_duration: float | None = None
        usage = body.get("usage") if isinstance(body, dict) else None
        if isinstance(usage, dict):
            raw_duration = usage.get("duration")
            if isinstance(raw_duration, (int, float)):
                usage_duration = float(raw_duration)
        request_id = body.get("request_id") if isinstance(body, dict) else None
        if not isinstance(request_id, str):
            request_id = None
        return ASRTranscription(
            transcript=transcript,
            provider=self.provider_name,
            model=self.model,
            request_id=request_id,
            usage_duration_seconds=usage_duration,
            latency_ms=latency_ms,
        )
