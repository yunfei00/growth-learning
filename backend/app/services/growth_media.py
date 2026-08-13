"""Private media persistence for exact-text manual growth records."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.object_storage import PrivateObjectStorage
from app.models import GrowthEvent, GrowthMediaAsset
from app.services.science_media import validate_media


async def persist_growth_media(
    session: AsyncSession,
    storage: PrivateObjectStorage,
    *,
    settings: Settings,
    event: GrowthEvent,
    family_id: uuid.UUID,
    uploader_user_id: uuid.UUID,
    filename: str | None,
    mime_type: str | None,
    content: bytes,
) -> GrowthMediaAsset:
    kind, extension, original_filename = validate_media(
        settings=settings, filename=filename, mime_type=mime_type, content=content
    )
    asset_id = uuid.uuid4()
    object_key = f"growth/{family_id}/{event.id}/{asset_id}{extension}"
    await storage.put(object_key, content, mime_type or "application/octet-stream")
    asset = GrowthMediaAsset(
        id=asset_id,
        growth_event_id=event.id,
        family_id=family_id,
        child_id=event.child_id,
        object_key=object_key,
        original_filename=original_filename,
        media_kind=kind,
        mime_type=mime_type or "application/octet-stream",
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


async def get_private_growth_media(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    event_id: uuid.UUID,
    media_id: uuid.UUID,
) -> GrowthMediaAsset | None:
    return await session.scalar(
        select(GrowthMediaAsset).where(
            GrowthMediaAsset.id == media_id,
            GrowthMediaAsset.child_id == child_id,
            GrowthMediaAsset.growth_event_id == event_id,
        )
    )
