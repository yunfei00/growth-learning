"""Safe English audio resolution with a strict phonics/letter-name boundary."""

import uuid
from dataclasses import dataclass

from app.models import EnglishItem
from app.services.english_catalog import DEFAULT_ENGLISH_ACCENT


@dataclass(frozen=True)
class EnglishAudio:
    strategy: str
    accent: str
    speech_text: str | None
    audio_url: str | None
    instruction_zh: str
    available: bool


class EnglishAudioProvider:
    """Resolve curated audio first, then safe deterministic fallbacks."""

    def resolve(self, item: EnglishItem) -> EnglishAudio:
        accent = item.audio_accent or DEFAULT_ENGLISH_ACCENT
        if item.audio_key:
            return EnglishAudio(
                strategy="curated",
                accent=accent,
                speech_text=None,
                audio_url=f"/api/v1/english/items/{item.knowledge_point_id}/audio",
                instruction_zh="播放正式英语音频",
                available=True,
            )
        metadata = item.metadata_json or {}
        if item.kind == "phonics":
            example = str(metadata.get("example_word", "")).strip()
            if example:
                role = str(metadata.get("audio_role", "safe_example_word"))
                instruction = (
                    f"把声音连起来，听完整单词 {example}。"
                    if role == "blend_word"
                    else f"听单词 {example}，留意目标位置的声音。"
                )
                return EnglishAudio(
                    strategy="safe_example_word",
                    accent=accent,
                    speech_text=example,
                    audio_url=None,
                    instruction_zh=instruction,
                    available=True,
                )
            return EnglishAudio(
                strategy="phonics_unavailable",
                accent=accent,
                speech_text=None,
                audio_url=None,
                instruction_zh="暂时没有可靠的发音音频，请由家长示范。",
                available=False,
            )
        return EnglishAudio(
            strategy="tts",
            accent=accent,
            speech_text=item.text,
            audio_url=None,
            instruction_zh="使用固定 en-US 英语语音播放",
            available=True,
        )

    def curated_object_key(self, item: EnglishItem, knowledge_point_id: uuid.UUID) -> str:
        if item.knowledge_point_id != knowledge_point_id or not item.audio_key:
            raise LookupError("Curated English audio is not configured")
        return item.audio_key


english_audio_provider = EnglishAudioProvider()
