"""Legal open-library discovery and child-private picture-book reading routes."""

import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from minio.error import S3Error
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.integrations.object_storage import PrivateObjectStorage, build_private_object_storage
from app.integrations.tts import DashScopeTTSProvider, TTSProviderError
from app.models.picture_book import PictureBookImport
from app.schemas.picture_book import (
    OpenPictureBookSummary,
    PictureBookDetail,
    PictureBookImportResponse,
)
from app.services.authorization import get_authorized_child
from app.services.gdl_picture_books import (
    GDLImportError,
    discover_gdl_books,
    import_gdl_picture_book,
    picture_book_detail,
    picture_page_object,
)
from app.services.story_audio import paragraph_audio_key, prepare_story_paragraph_audio

router = APIRouter(prefix="/children", tags=["picture-books"])


def get_picture_storage(request: Request) -> PrivateObjectStorage:
    return build_private_object_storage(request.app.state.settings)


PictureStorage = Annotated[PrivateObjectStorage, Depends(get_picture_storage)]


def _tts_provider(request: Request) -> DashScopeTTSProvider | None:
    settings = request.app.state.settings
    if not settings.reading_tts_configured:
        return None
    return DashScopeTTSProvider(
        api_key=settings.literacy_asr_api_key.get_secret_value(),
        base_url=settings.literacy_asr_base_url,
        model=settings.reading_tts_model,
        voice=settings.reading_tts_voice,
        timeout_seconds=settings.reading_tts_timeout_seconds,
    )


@router.get("/{child_id}/open-picture-books", response_model=list[OpenPictureBookSummary])
async def list_open_picture_books(
    child_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    level: str | None = Query(default=None, pattern="^[12]$"),
) -> list[OpenPictureBookSummary]:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await discover_gdl_books(level=level)
    except (GDLImportError, httpx.HTTPError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="在线绘本库暂时不可用，请稍后重试",
        ) from error


@router.post(
    "/{child_id}/open-picture-books/gdl/{source_book_id}/import",
    response_model=PictureBookImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_open_picture_book(
    child_id: uuid.UUID,
    source_book_id: str,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
    storage: PictureStorage,
) -> PictureBookImportResponse:
    child, _ = await get_authorized_child(session, current_user, child_id, admin_required=True)
    if not source_book_id.isdigit():
        raise HTTPException(status_code=422, detail="绘本编号无效")
    try:
        picture, version, imported = await import_gdl_picture_book(
            session,
            storage,
            child=child,
            imported_by_user_id=current_user.id,
            source_book_id=source_book_id,
        )
    except GDLImportError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="GDL 内容下载失败，请稍后重试") from error
    except S3Error as error:
        raise HTTPException(status_code=503, detail="绘本图片保存失败，请稍后重试") from error

    audio_prepared = False
    tts = _tts_provider(request)
    if tts is not None:
        try:
            await prepare_story_paragraph_audio(
                storage,
                tts,
                child_id=child_id,
                version=version,
            )
            audio_prepared = True
        except (TTSProviderError, S3Error, ValueError):
            pass
    return PictureBookImportResponse(
        picture_book_id=picture.id,
        story_version_id=version.id,
        imported=imported,
        audio_prepared=audio_prepared,
    )


@router.get(
    "/{child_id}/story-versions/{story_version_id}/picture-book",
    response_model=PictureBookDetail,
)
async def get_picture_book(
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> PictureBookDetail:
    await get_authorized_child(session, current_user, child_id)
    result = await picture_book_detail(
        session, child_id=child_id, story_version_id=story_version_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Picture book not found")
    return result


@router.get("/{child_id}/story-versions/{story_version_id}/picture/pages/{page_index}/image")
async def get_picture_page_image(
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    page_index: int,
    session: DbSession,
    current_user: CurrentUser,
    storage: PictureStorage,
) -> Response:
    await get_authorized_child(session, current_user, child_id)
    picture = await session.scalar(
        select(PictureBookImport).where(
            PictureBookImport.child_id == child_id,
            PictureBookImport.story_version_id == story_version_id,
        )
    )
    if picture is None:
        raise HTTPException(status_code=404, detail="Picture book not found")
    object_info = picture_page_object(picture, page_index)
    if object_info is None:
        raise HTTPException(status_code=404, detail="Page image not found")
    object_key, mime = object_info
    try:
        content = await storage.read(object_key)
    except S3Error as error:
        raise HTTPException(status_code=404, detail="Page image not found") from error
    return Response(content=content, media_type=mime, headers={"Cache-Control": "private, max-age=3600"})


@router.post("/{child_id}/story-versions/{story_version_id}/picture/audio/prepare")
async def prepare_picture_book_audio(
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
    storage: PictureStorage,
) -> dict[str, object]:
    await get_authorized_child(session, current_user, child_id, admin_required=True)
    picture = await session.scalar(
        select(PictureBookImport).where(
            PictureBookImport.child_id == child_id,
            PictureBookImport.story_version_id == story_version_id,
        )
    )
    if picture is None:
        raise HTTPException(status_code=404, detail="Picture book not found")
    from app.models import StoryVersion

    version = await session.get(StoryVersion, story_version_id)
    tts = _tts_provider(request)
    if version is None:
        raise HTTPException(status_code=404, detail="Picture book not found")
    if tts is None:
        raise HTTPException(status_code=503, detail="故事朗读服务尚未配置")
    try:
        count = await prepare_story_paragraph_audio(
            storage, tts, child_id=child_id, version=version
        )
    except TTSProviderError as error:
        raise HTTPException(status_code=503, detail="绘本音频生成失败，请稍后重试") from error
    return {"prepared": True, "pages": count, "model": tts.model, "voice": tts.voice}


@router.get("/{child_id}/story-versions/{story_version_id}/picture/audio/pages/{page_index}")
async def get_picture_page_audio(
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    page_index: int,
    session: DbSession,
    current_user: CurrentUser,
    storage: PictureStorage,
) -> Response:
    await get_authorized_child(session, current_user, child_id)
    picture = await session.scalar(
        select(PictureBookImport.id).where(
            PictureBookImport.child_id == child_id,
            PictureBookImport.story_version_id == story_version_id,
        )
    )
    if picture is None:
        raise HTTPException(status_code=404, detail="Picture book not found")
    from app.models import StoryVersion

    version = await session.get(StoryVersion, story_version_id)
    if version is None or page_index < 0 or page_index >= len(version.paragraphs):
        raise HTTPException(status_code=404, detail="Page audio not found")
    key = paragraph_audio_key(child_id, story_version_id, page_index)
    try:
        content = await storage.read(key)
    except S3Error as error:
        raise HTTPException(status_code=404, detail="Page audio not ready") from error
    return Response(content=content, media_type="audio/x-wav", headers={"Cache-Control": "private, max-age=3600"})
