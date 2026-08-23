"""Validated private media persistence for one authorized experiment session."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
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
logger = logging.getLogger(__name__)


class ScienceMediaValidationError(ValueError):
    pass


def _matches_declared_media_type(mime_type: str, content: bytes) -> bool:
    """Apply bounded magic-byte checks before private object persistence."""
    if mime_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if mime_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    if mime_type == "video/mp4":
        return len(content) >= 12 and content[4:8] == b"ftyp"
    if mime_type in {"video/webm", "audio/webm"}:
        return content.startswith(b"\x1aE\xdf\xa3")
    if mime_type == "audio/mpeg":
        return content.startswith(b"ID3") or (
            len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0
        )
    if mime_type == "audio/wav":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE"
    if mime_type == "audio/ogg":
        return content.startswith(b"OggS")
    return False


def _safe_original_filename(filename: str | None, extension: str) -> str:
    candidate = (filename or f"experiment{extension}").replace("\\", "/").split("/")[-1]
    candidate = "".join(
        character for character in candidate if character >= " " and character != "\x7f"
    )
    candidate = candidate.strip(" .")[:180]
    if candidate in {"", ".", ".."}:
        return f"experiment{extension}"
    return candidate


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
    if not _matches_declared_media_type(normalized_type, content):
        raise ScienceMediaValidationError("媒体文件内容与声明类型不一致")
    original_filename = _safe_original_filename(filename, extension)
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
    experiment_session.updated_at = datetime.now(UTC)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await storage.remove(object_key)
        raise
    await session.refresh(asset)
    return asset


async def delete_experiment_media(
    session: AsyncSession,
    storage: PrivateObjectStorage,
    *,
    experiment_session: ExperimentSession,
    asset: ExperimentMediaAsset,
) -> None:
    object_key = asset.object_key
    await session.execute(delete(ExperimentMediaAsset).where(ExperimentMediaAsset.id == asset.id))
    experiment_session.updated_at = datetime.now(UTC)
    await session.commit()
    try:
        await storage.remove(object_key)
    except Exception:
        logger.exception(
            "Failed to remove deleted experiment media object", extra={"object_key": object_key}
        )


async def replace_experiment_media(
    session: AsyncSession,
    storage: PrivateObjectStorage,
    *,
    settings: Settings,
    experiment_session: ExperimentSession,
    asset: ExperimentMediaAsset,
    uploader_user_id: uuid.UUID,
    filename: str | None,
    mime_type: str | None,
    content: bytes,
) -> ExperimentMediaAsset:
    kind, extension, original_filename = validate_media(
        settings=settings, filename=filename, mime_type=mime_type, content=content
    )
    old_object_key = asset.object_key
    new_object_key = f"science/{asset.family_id}/{experiment_session.id}/{uuid.uuid4()}{extension}"
    await storage.put(new_object_key, content, mime_type or "application/octet-stream")
    asset.object_key = new_object_key
    asset.original_filename = original_filename
    asset.media_kind = kind
    asset.mime_type = mime_type or "application/octet-stream"
    asset.size_bytes = len(content)
    asset.uploader_user_id = uploader_user_id
    asset.created_at = datetime.now(UTC)
    experiment_session.updated_at = datetime.now(UTC)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await storage.remove(new_object_key)
        raise
    await session.refresh(asset)
    try:
        await storage.remove(old_object_key)
    except Exception:
        logger.exception(
            "Failed to remove replaced experiment media object",
            extra={"object_key": old_object_key},
        )
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
