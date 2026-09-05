"""Cached server-side narration for household-private stories."""

from __future__ import annotations

import uuid

from app.integrations.object_storage import PrivateObjectStorage
from app.integrations.tts import DashScopeTTSProvider
from app.models import StoryVersion


def paragraph_audio_key(child_id: uuid.UUID, version_id: uuid.UUID, paragraph_index: int) -> str:
    if paragraph_index < 0:
        raise ValueError("paragraph index cannot be negative")
    return f"stories/{child_id}/{version_id}/audio/paragraph-{paragraph_index:03d}.wav"


async def prepare_story_paragraph_audio(
    storage: PrivateObjectStorage,
    provider: DashScopeTTSProvider,
    *,
    child_id: uuid.UUID,
    version: StoryVersion,
) -> int:
    """Synthesize every paragraph once and persist provider-independent WAV bytes."""

    prepared = 0
    for index, paragraph in enumerate(version.paragraphs):
        synthesis = await provider.synthesize(paragraph)
        await storage.put(
            paragraph_audio_key(child_id, version.id, index),
            synthesis.audio,
            synthesis.mime_type,
        )
        prepared += 1
    return prepared
