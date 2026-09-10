"""Legal open-library discovery and child-private picture-book reading routes."""

import json
import uuid
from contextlib import suppress
from typing import Annotated

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from minio.error import S3Error
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.integrations.object_storage import PrivateObjectStorage, build_private_object_storage
from app.integrations.tts import DashScopeTTSProvider, TTSProviderError
from app.models import Story, StoryVersion
from app.models.picture_book import PictureBookImport
from app.schemas.picture_book import (
    FamilyPictureBookUpdateRequest,
    OpenPictureBookSummary,
    PictureBookDetail,
    PictureBookImportResponse,
)
from app.schemas.story import ParentStoryCreateRequest
from app.services.authorization import get_authorized_child
from app.services.gdl_picture_books import (
    GDLImportError,
    discover_gdl_books,
    import_gdl_picture_book,
    picture_book_detail,
    picture_page_object,
)
from app.services.manual_story import create_parent_story
from app.services.story_audio import paragraph_audio_key, prepare_story_paragraph_audio

router = APIRouter(prefix="/children", tags=["picture-books"])

FAMILY_PICTURE_PROVIDER = "family_upload"
FAMILY_PICTURE_THEME = "open_picture_book"
MAX_PICTURE_BOOK_PAGES = 24
MAX_PAGE_TEXT_CHARS = 220
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


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


def _parse_page_texts(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="绘本页文字格式无效") from error
    if not isinstance(value, list):
        raise HTTPException(status_code=422, detail="绘本页文字格式无效")
    texts = [str(item).strip() for item in value]
    if not texts or len(texts) > MAX_PICTURE_BOOK_PAGES:
        raise HTTPException(status_code=422, detail="绘本需要 1～24 页正文")
    if any(not text for text in texts):
        raise HTTPException(status_code=422, detail="每一页都需要填写文字")
    if any(len(text) > MAX_PAGE_TEXT_CHARS for text in texts):
        raise HTTPException(status_code=422, detail="单页文字不能超过 220 个字符")
    return texts


async def _read_image(upload: UploadFile, *, label: str) -> tuple[bytes, str, str]:
    mime = (upload.content_type or "").lower()
    extension = ALLOWED_IMAGE_TYPES.get(mime)
    if extension is None:
        raise HTTPException(status_code=422, detail=f"{label}仅支持 JPG、PNG、WebP 图片")
    content = await upload.read(MAX_IMAGE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail=f"{label}图片为空")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"{label}不能超过 8 MB")
    return content, mime, extension


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
    "/{child_id}/picture-books/manual",
    response_model=PictureBookImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_family_picture_book(
    child_id: uuid.UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
    storage: PictureStorage,
    title: str = Form(..., min_length=1, max_length=120),
    page_texts: str = Form(...),
    images: list[UploadFile] = File(...),
    cover: UploadFile | None = File(default=None),
) -> PictureBookImportResponse:
    """Create a household-private picture book from parent supplied page images and text."""

    child, _ = await get_authorized_child(session, current_user, child_id, admin_required=True)
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=422, detail="请填写绘本标题")
    texts = _parse_page_texts(page_texts)
    if len(images) != len(texts):
        raise HTTPException(status_code=422, detail="正文图片数量必须和页数一致")
    if len(images) > MAX_PICTURE_BOOK_PAGES:
        raise HTTPException(status_code=422, detail="绘本最多支持 24 页正文")

    try:
        run, version = await create_parent_story(
            session,
            child=child,
            created_by_user_id=current_user.id,
            payload=ParentStoryCreateRequest(title=clean_title, content="\n".join(texts)),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if len(version.paragraphs) != len(texts):
        raise HTTPException(status_code=422, detail="绘本页文字无法保持一页一段，请精简单页文字")

    stored_keys: list[str] = []
    page_payloads: list[dict[str, object]] = []
    cover_object_key: str | None = None
    try:
        for position, upload in enumerate(images):
            content, mime, extension = await _read_image(upload, label=f"第 {position + 1} 页")
            object_key = f"picture-books/{child.id}/{version.id}/pages/{position:03d}.{extension}"
            await storage.put(object_key, content, mime)
            stored_keys.append(object_key)
            page_payloads.append(
                {
                    "position": position,
                    "text": texts[position],
                    "image_object_key": object_key,
                    "image_mime_type": mime,
                    "image_alt": f"{clean_title} 第 {position + 1} 页插图",
                    "source_image_url": None,
                }
            )

        if cover is not None:
            content, mime, extension = await _read_image(cover, label="封面")
            cover_object_key = f"picture-books/{child.id}/{version.id}/cover.{extension}"
            await storage.put(cover_object_key, content, mime)
            stored_keys.append(cover_object_key)

        story = await session.get(Story, version.story_id)
        if story is not None:
            story.theme = FAMILY_PICTURE_THEME
        run.theme = FAMILY_PICTURE_THEME
        version.theme = FAMILY_PICTURE_THEME

        picture = PictureBookImport(
            child_id=child.id,
            story_version_id=version.id,
            imported_by_user_id=current_user.id,
            source_provider=FAMILY_PICTURE_PROVIDER,
            source_book_id=str(uuid.uuid4()),
            source_h5p_id=None,
            source_url="",
            license_name="家庭私有内容",
            reading_level="亲子共读",
            attribution={
                "title": clean_title,
                "source": "家庭上传",
                "private": True,
                "uploaded_by": str(current_user.id),
            },
            pages=page_payloads,
            cover_object_key=cover_object_key or page_payloads[0]["image_object_key"],
        )
        session.add(picture)
        await session.commit()
        await session.refresh(picture)
        await session.refresh(version)
    except HTTPException:
        await session.rollback()
        for key in stored_keys:
            with suppress(Exception):
                await storage.remove(key)
        raise
    except S3Error as error:
        await session.rollback()
        for key in stored_keys:
            with suppress(Exception):
                await storage.remove(key)
        raise HTTPException(status_code=503, detail="绘本图片保存失败，请稍后重试") from error
    except Exception:
        await session.rollback()
        for key in stored_keys:
            with suppress(Exception):
                await storage.remove(key)
        raise

    audio_prepared = False
    tts = _tts_provider(request)
    if tts is not None:
        try:
            await prepare_story_paragraph_audio(storage, tts, child_id=child_id, version=version)
            audio_prepared = True
        except (TTSProviderError, S3Error, ValueError):
            pass
    return PictureBookImportResponse(
        picture_book_id=picture.id,
        story_version_id=version.id,
        imported=True,
        audio_prepared=audio_prepared,
    )


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
            await prepare_story_paragraph_audio(storage, tts, child_id=child_id, version=version)
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
    result = await picture_book_detail(session, child_id=child_id, story_version_id=story_version_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Picture book not found")
    return result


@router.put(
    "/{child_id}/story-versions/{story_version_id}/picture-book/manual",
    response_model=PictureBookDetail,
)
async def update_family_picture_book(
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    payload: FamilyPictureBookUpdateRequest,
    session: DbSession,
    current_user: CurrentUser,
    storage: PictureStorage,
) -> PictureBookDetail:
    """Edit title and page text for a household-uploaded picture book."""

    await get_authorized_child(session, current_user, child_id, admin_required=True)
    picture = await session.scalar(
        select(PictureBookImport).where(
            PictureBookImport.child_id == child_id,
            PictureBookImport.story_version_id == story_version_id,
        )
    )
    if picture is None:
        raise HTTPException(status_code=404, detail="Picture book not found")
    if picture.source_provider != FAMILY_PICTURE_PROVIDER:
        raise HTTPException(status_code=403, detail="只有家庭自己上传的绘本可以编辑")

    version = await session.get(StoryVersion, story_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Picture book not found")
    if len(payload.page_texts) != len(picture.pages):
        raise HTTPException(status_code=422, detail="编辑时页数必须保持不变")

    version.title = payload.title
    version.paragraphs = payload.page_texts
    updated_pages: list[dict[str, object]] = []
    for index, stored_page in enumerate(picture.pages):
        page = dict(stored_page)
        page["text"] = payload.page_texts[index]
        page["image_alt"] = f"{payload.title} 第 {index + 1} 页插图"
        updated_pages.append(page)
    picture.pages = updated_pages
    picture.attribution = {**picture.attribution, "title": payload.title}
    await session.commit()
    await session.refresh(picture)
    await session.refresh(version)

    # Existing narration no longer matches edited text, so remove it. It will be regenerated
    # automatically the next time the parent taps narration.
    for index in range(len(payload.page_texts)):
        with suppress(Exception):
            await storage.remove(paragraph_audio_key(child_id, story_version_id, index))

    result = await picture_book_detail(session, child_id=child_id, story_version_id=story_version_id)
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
    return Response(
        content=content,
        media_type=mime,
        headers={"Cache-Control": "private, max-age=3600"},
    )


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

    version = await session.get(StoryVersion, story_version_id)
    tts = _tts_provider(request)
    if version is None:
        raise HTTPException(status_code=404, detail="Picture book not found")
    if tts is None:
        raise HTTPException(status_code=503, detail="故事朗读服务尚未配置")
    try:
        count = await prepare_story_paragraph_audio(storage, tts, child_id=child_id, version=version)
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

    version = await session.get(StoryVersion, story_version_id)
    if version is None or page_index < 0 or page_index >= len(version.paragraphs):
        raise HTTPException(status_code=404, detail="Page audio not found")
    key = paragraph_audio_key(child_id, story_version_id, page_index)
    try:
        content = await storage.read(key)
    except S3Error as error:
        raise HTTPException(status_code=404, detail="Page audio not ready") from error
    return Response(
        content=content,
        media_type="audio/x-wav",
        headers={"Cache-Control": "private, max-age=3600"},
    )
