"""Safe audio selection for Pinyin without English letter-name fallback."""

import re
import uuid
from dataclasses import dataclass

from app.models import PinyinItem, PinyinPracticeItem

_SHORT_HAN_TARGET = re.compile(r"^[\u3400-\u9fff]$")
_TARGET_PURPOSE = "target_pronunciation"


@dataclass(frozen=True)
class PinyinAudio:
    mode: str
    audio_url: str | None
    speech_text: str | None
    purpose: str
    target_pronunciation: str


class PinyinAudioProvider:
    """Resolve only target pronunciation audio, never teaching or example copy."""

    def _from_metadata(
        self,
        metadata: dict[str, object],
        *,
        curated_url: str | None = None,
        default_target: str,
        allow_proxy: bool = True,
    ) -> PinyinAudio:
        target = str(metadata.get("target_pronunciation") or default_target).strip()
        if curated_url:
            return PinyinAudio(
                mode="curated",
                audio_url=curated_url,
                speech_text=None,
                purpose=_TARGET_PURPOSE,
                target_pronunciation=target,
            )

        # A proxy is allowed only when a human explicitly verified one Han target syllable.
        # This prevents Latin b/p/... from becoming English letter names and prevents
        # explanation/example sentences from leaking into listening assessments.
        target_audio_text = str(metadata.get("target_audio_text") or "").strip()
        if (
            allow_proxy
            and metadata.get("target_audio_text_verified") is True
            and _SHORT_HAN_TARGET.fullmatch(target_audio_text)
        ):
            return PinyinAudio(
                mode="tts_fallback",
                audio_url=None,
                speech_text=target_audio_text,
                purpose=_TARGET_PURPOSE,
                target_pronunciation=target,
            )
        return PinyinAudio(
            mode="missing",
            audio_url=None,
            speech_text=None,
            purpose=_TARGET_PURPOSE,
            target_pronunciation=target,
        )

    def resolve(self, item: PinyinItem) -> PinyinAudio:
        return self._from_metadata(
            item.metadata_json or {},
            curated_url=(
                f"/api/v1/pinyin/items/{item.knowledge_point_id}/audio" if item.audio_key else None
            ),
            default_target=item.display_text,
            allow_proxy=item.kind != "tone",
        )

    def resolve_practice(self, practice: PinyinPracticeItem) -> PinyinAudio:
        return self._from_metadata(
            practice.metadata_json or {},
            default_target=practice.display_syllable,
        )

    def curated_object_key(self, item: PinyinItem, knowledge_point_id: uuid.UUID) -> str:
        if item.knowledge_point_id != knowledge_point_id or not item.audio_key:
            raise LookupError("Curated Pinyin audio is not configured")
        return item.audio_key


pinyin_audio_provider = PinyinAudioProvider()
