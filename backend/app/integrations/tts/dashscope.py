"""DashScope Qwen3-TTS adapter that immediately downloads ephemeral audio.

Alibaba returns a short-lived audio URL.  This adapter downloads the generated
WAV bytes immediately so callers can persist them in household-private object
storage and never depend on the provider URL during child playback.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx


class TTSProviderError(RuntimeError):
    """The configured TTS provider could not synthesize usable audio."""


@dataclass(frozen=True)
class TTSSynthesis:
    audio: bytes
    mime_type: str
    provider: str
    model: str
    voice: str
    request_id: str | None
    character_count: int | None


class DashScopeTTSProvider:
    provider_name = "dashscope_qwen3_tts"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = "qwen3-tts-flash",
        voice: str = "Cherry",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.strip()
        self.model = model.strip()
        self.voice = voice.strip()
        self.timeout_seconds = timeout_seconds
        if not self.api_key or not self.base_url or not self.model or not self.voice:
            raise TTSProviderError("Reading TTS is not configured")

    async def synthesize(self, text: str) -> TTSSynthesis:
        speech_text = text.strip()
        if not speech_text:
            raise TTSProviderError("TTS text cannot be blank")
        payload = {
            "model": self.model,
            "input": {
                "text": speech_text,
                "voice": self.voice,
                "language_type": "Chinese",
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.base_url, headers=headers, json=payload)
                if response.status_code >= 400:
                    raise TTSProviderError(f"Reading TTS returned HTTP {response.status_code}")
                try:
                    body = response.json()
                except ValueError as error:
                    raise TTSProviderError("Reading TTS returned invalid JSON") from error
                output = body.get("output") if isinstance(body, dict) else None
                audio = output.get("audio") if isinstance(output, dict) else None
                audio_url = audio.get("url") if isinstance(audio, dict) else None
                if not isinstance(audio_url, str) or not audio_url:
                    raise TTSProviderError("Reading TTS did not return an audio URL")
                audio_response = await client.get(audio_url)
                if audio_response.status_code >= 400:
                    raise TTSProviderError(
                        f"Reading TTS audio download returned HTTP {audio_response.status_code}"
                    )
                audio_bytes = audio_response.content
        except httpx.RequestError as error:
            raise TTSProviderError("Reading TTS could not be reached") from error
        if not audio_bytes:
            raise TTSProviderError("Reading TTS returned empty audio")

        request_id = body.get("request_id") if isinstance(body, dict) else None
        if not isinstance(request_id, str):
            request_id = None
        usage = body.get("usage") if isinstance(body, dict) else None
        character_count = usage.get("characters") if isinstance(usage, dict) else None
        if not isinstance(character_count, int):
            character_count = None
        mime_type = audio_response.headers.get("content-type", "audio/wav").split(";", 1)[0]
        if not mime_type.startswith("audio/"):
            mime_type = "audio/wav"
        return TTSSynthesis(
            audio=audio_bytes,
            mime_type=mime_type,
            provider=self.provider_name,
            model=self.model,
            voice=self.voice,
            request_id=request_id,
            character_count=character_count,
        )
