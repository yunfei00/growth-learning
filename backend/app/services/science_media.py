"""Validated private media persistence for one authorized experiment session."""

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.object_storage import PrivateObjectStorage
from app.models import ExperimentMediaAsset, ExperimentMediaKind, ExperimentSession

ALLOWED_MEDIA: dict[str, tuple[str, str]] = {
    "image/jpeg": (ExperimentMediaKind.IMAGE, ".jpg"),
    "image/png": (ExperimentMediaKind.IMAGE, ".png"),
    "image/webp": (ExperimentMediaKind.IMAGE, ".webp"),
    "video/mp4": (ExperimentMediaKind.VIDEO, ".mp4"),
    "video/webm": (ExperimentMediaKind.VIDEO, ".webm"),
    "audio/mpeg": (ExperimentMediaKind.AUDIO, ".mp3"),
    "audio/wav": (ExperimentMediaKind.AUDIO, ".wav"),
    "audio/webm": (ExperimentMediaKind.AUDIO, ".webm"),
    "audio/ogg": (ExperimentMediaKind.AUDIO, ".ogg"),
}


class ScienceMediaValidationError(ValueError):
    pass


def media_limit(settings: Settings, kind: str) -> int:
    if kind == ExperimentMediaKind.IMAGE:
        return settings.science_image_max_bytes
    if kind == ExperimentMediaKind.VIDEO:
        return settings.science_video_max_bytes
    return settings.science_audio_max_bytes


def validate_media(
    *, settings: Settings, filename: str | None, mime_type: str | None, content: bytes
) -> tuple[str, str, str]:
    normalized_type = (mime_type or "").lower().strip()
    media = ALLOWED_MEDIA.get(normalized_type)
    if media is None:
        raise ScienceMediaValidationError("仅支持 JPEG/PNG/WebP 图片、MP4/WebM 视频和常见音频")
    kind, extension = media
    if not content:
        raise ScienceMediaValidationError("媒体文件不能为空")
    if len(content) > media_limit(settings, kind):
        raise ScienceMediaValidationError("媒体文件超过允许大小")
    original_filename = Path(filename or f"experiment{extension}").name[:255]
    if not original_filename:
        original_filename = f"experiment{extension}"
    return kind, extension, original_filename


async def persist_experiment_media(
    session: AsyncSession,
    storage: PrivateObjectStorage,
    *,
    settings: Settings,
    experiment_session: ExperimentSession,
    family_id: uuid.UUID,
    uploader_user_id: uuid.UUID,
    filename: str | None,
    mime_type: str | None,
    content: bytes,
) -> ExperimentMediaAsset:
    kind, extension, original_filename = validate_media(
        settings=settings, filename=filename, mime_type=mime_type, content=content
    )
    asset_id = uuid.uuid4()
    object_key = f"science/{family_id}/{experiment_session.id}/{asset_id}{extension}"
    await storage.put(object_key, content, mime_type or "application/octet-stream")
    asset = ExperimentMediaAsset(
        id=asset_id,
        experiment_session_id=experiment_session.id,
        family_id=family_id,
        child_id=experiment_session.child_id,
        object_key=object_key,
        original_filename=original_filename,
        media_kind=kind,
        mime_type=mime_type,
        size_bytes=len(content),
        uploader_user_id=uploader_user_id,
    )
    session.add(asset)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await storage.remove(object_key)
        raise
    await session.refresh(asset)
    return asset


async def get_private_media_asset(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    experiment_session_id: uuid.UUID,
    media_id: uuid.UUID,
) -> ExperimentMediaAsset | None:
    return await session.scalar(
        select(ExperimentMediaAsset).where(
            ExperimentMediaAsset.id == media_id,
            ExperimentMediaAsset.child_id == child_id,
            ExperimentMediaAsset.experiment_session_id == experiment_session_id,
        )
    )
