"""Safe audio selection for Pinyin without English letter-name fallback."""

import re
import uuid
from dataclasses import dataclass

from app.models import PinyinItem

_HAN_CHARACTER = re.compile(r"[\u3400-\u9fff]")


@dataclass(frozen=True)
class PinyinAudio:
    mode: str
    audio_url: str | None
    speech_text: str | None


class PinyinAudioProvider:
    """Prefer curated audio; otherwise expose only a Chinese speech cue."""

    def resolve(self, item: PinyinItem) -> PinyinAudio:
        if item.audio_key:
            return PinyinAudio(
                mode="curated",
                audio_url=f"/api/v1/pinyin/items/{item.knowledge_point_id}/audio",
                speech_text=None,
            )
        cue = (item.pronunciation_cue or "").strip()
        if cue and _HAN_CHARACTER.search(cue):
            return PinyinAudio(mode="tts_fallback", audio_url=None, speech_text=cue)
        return PinyinAudio(mode="missing", audio_url=None, speech_text=None)

    def curated_object_key(self, item: PinyinItem, knowledge_point_id: uuid.UUID) -> str:
        if item.knowledge_point_id != knowledge_point_id or not item.audio_key:
            raise LookupError("Curated Pinyin audio is not configured")
        return item.audio_key


pinyin_audio_provider = PinyinAudioProvider()
