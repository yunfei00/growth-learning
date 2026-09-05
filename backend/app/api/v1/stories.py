"""Mastery-aware generation plus parent-authored household-private reading routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from minio.error import S3Error

from app.api.dependencies import CurrentUser, DbSession
from app.integrations.ai.base import AIProvider
from app.integrations.ai.factory import build_ai_provider
from app.integrations.object_storage import PrivateObjectStorage, build_private_object_storage
from app.integrations.tts import DashScopeTTSProvider, TTSProviderError
from app.schemas.story import (
    ParentStoryCreateRequest,
    ReadingAnswersSubmit,
    ReadingCompleteRequest,
    ReadingSessionResponse,
    ReadingSessionStart,
    ReadingSummaryResponse,
    StoryGenerationContextResponse,
    StoryGenerationRequest,
    StoryGenerationResponse,
    StoryPageResponse,
    StoryVersionResponse,
)
from app.services.authorization import get_authorized_child
from app.services.manual_story import create_parent_story
from app.services.story_audio import paragraph_audio_key, prepare_story_paragraph_audio
from app.services.story_generation import (
    StoryGenerationError,
    generate_story,
    generation_context,
)
from app.services.story_reading import (
    complete_reading,
    get_private_story_version,
    list_storybook,
    reading_summary,
    start_or_resume_reading,
    story_version_response,
    submit_reading_answers,
)

router = APIRouter(prefix="/children", tags=["stories"])


def get_story_ai_provider(request: Request) -> AIProvider:
    return build_ai_provider(request.app.state.settings)


def get_story_storage(request: Request) -> PrivateObjectStorage:
    return build_private_object_storage(request.app.state.settings)


StoryAIProvider = Annotated[AIProvider, Depends(get_story_ai_provider)]
StoryStorage = Annotated[PrivateObjectStorage, Depends(get_story_storage)]


def _provider_config(request: Request) -> tuple[bool, str, str]:
    settings = request.app.state.settings
    configured = bool(
        settings.ai_provider != "disabled"
        and settings.ai_api_key.get_secret_value()
        and settings.ai_model
    )
    return configured, settings.ai_provider, settings.ai_model


def _story_tts_provider(request: Request) -> DashScopeTTSProvider | None:
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


@router.get("/{child_id}/reading-context", response_model=StoryGenerationContextResponse)
async def get_reading_context(
    child_id: uuid.UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
) -> StoryGenerationContextResponse:
    child, _ = await get_authorized_child(session, current_user, child_id)
    configured, provider, model = _provider_config(request)
    return await generation_context(
        session,
        child,
        provider_configured=configured,
        provider=provider,
        model=model,
    )


@router.post(
    "/{child_id}/stories/generate",
    response_model=StoryGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_story(
    child_id: uuid.UUID,
    payload: StoryGenerationRequest,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
    provider: StoryAIProvider,
) -> StoryGenerationResponse:
    child, _ = await get_authorized_child(session, current_user, child_id, admin_required=True)
    configured, provider_name, model = _provider_config(request)
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 服务尚未配置",
        )
    try:
        run, version = await generate_story(
            session,
            child=child,
            requested_by_user_id=current_user.id,
            payload=payload,
            provider=provider,
            provider_name=provider_name,
            configured_model=model,
            max_attempts=request.app.state.settings.ai_story_max_attempts,
        )
    except StoryGenerationError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return StoryGenerationResponse(
        generation_run_id=run.id,
        status="succeeded",
        attempt_count=run.attempt_count,
        version=await story_version_response(session, child_id, version),
    )


@router.post(
    "/{child_id}/stories/manual",
    response_model=StoryGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_story(
    child_id: uuid.UUID,
    payload: ParentStoryCreateRequest,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
) -> StoryGenerationResponse:
    """Save a parent-pasted story without literacy gating and prepare narration."""

    child, _ = await get_authorized_child(session, current_user, child_id, admin_required=True)
    try:
        run, version = await create_parent_story(
            session,
            child=child,
            created_by_user_id=current_user.id,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    tts = _story_tts_provider(request)
    if tts is not None:
        try:
            storage = build_private_object_storage(request.app.state.settings)
            await prepare_story_paragraph_audio(
                storage,
                tts,
                child_id=child_id,
                version=version,
            )
        except (TTSProviderError, S3Error, ValueError):
            # The authored story is already safely persisted. Narration is a
            # recoverable enhancement and must never destroy the reading item.
            pass

    return StoryGenerationResponse(
        generation_run_id=run.id,
        status="succeeded",
        attempt_count=run.attempt_count,
        version=await story_version_response(session, child_id, version),
    )


@router.post("/{child_id}/story-versions/{story_version_id}/audio/prepare")
async def prepare_story_audio(
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
    storage: StoryStorage,
) -> dict[str, object]:
    await get_authorized_child(session, current_user, child_id, admin_required=True)
    row = await get_private_story_version(session, child_id, story_version_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Story version not found")
    _, version = row
    tts = _story_tts_provider(request)
    if tts is None:
        raise HTTPException(status_code=503, detail="故事朗读服务尚未配置")
    try:
        count = await prepare_story_paragraph_audio(
            storage,
            tts,
            child_id=child_id,
            version=version,
        )
    except TTSProviderError as error:
        raise HTTPException(status_code=503, detail="故事音频生成失败，请稍后重试") from error
    return {"prepared": True, "segments": count, "model": tts.model, "voice": tts.voice}


@router.get(
    "/{child_id}/story-versions/{story_version_id}/audio/paragraphs/{paragraph_index}",
    response_class=Response,
)
async def get_story_paragraph_audio(
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    paragraph_index: int,
    session: DbSession,
    current_user: CurrentUser,
    storage: StoryStorage,
) -> Response:
    await get_authorized_child(session, current_user, child_id)
    row = await get_private_story_version(session, child_id, story_version_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Story version not found")
    _, version = row
    if paragraph_index < 0 or paragraph_index >= len(version.paragraphs):
        raise HTTPException(status_code=404, detail="Story paragraph not found")
    try:
        content = await storage.read(paragraph_audio_key(child_id, version.id, paragraph_index))
    except S3Error as error:
        raise HTTPException(status_code=404, detail="Story narration not prepared") from error
    return Response(
        content=content,
        media_type="audio/wav",
        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/{child_id}/stories", response_model=StoryPageResponse)
async def get_storybook(
    child_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    search: str | None = Query(default=None, max_length=80),
    difficulty: str | None = Query(default=None, pattern="^(beginner|normal|challenge)$"),
) -> StoryPageResponse:
    await get_authorized_child(session, current_user, child_id)
    return await list_storybook(
        session,
        child_id,
        page=page,
        page_size=page_size,
        search=search,
        difficulty=difficulty,
    )


@router.get("/{child_id}/story-versions/{story_version_id}", response_model=StoryVersionResponse)
async def get_story_version(
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> StoryVersionResponse:
    await get_authorized_child(session, current_user, child_id)
    row = await get_private_story_version(session, child_id, story_version_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Story version not found")
    _, version = row
    return await story_version_response(session, child_id, version)


@router.post(
    "/{child_id}/story-versions/{story_version_id}/reading/start",
    response_model=ReadingSessionResponse,
)
async def start_reading(
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    payload: ReadingSessionStart,
    session: DbSession,
    current_user: CurrentUser,
) -> ReadingSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await start_or_resume_reading(
            session,
            child_id=child_id,
            story_version_id=story_version_id,
            evaluator_user_id=current_user.id,
            payload=payload,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/{child_id}/reading-sessions/{reading_session_id}/answers",
    response_model=ReadingSessionResponse,
)
async def answer_questions(
    child_id: uuid.UUID,
    reading_session_id: uuid.UUID,
    payload: ReadingAnswersSubmit,
    session: DbSession,
    current_user: CurrentUser,
) -> ReadingSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await submit_reading_answers(
            session,
            child_id=child_id,
            reading_session_id=reading_session_id,
            evaluator_user_id=current_user.id,
            payload=payload,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/{child_id}/reading-sessions/{reading_session_id}/complete",
    response_model=ReadingSessionResponse,
)
async def finish_reading(
    child_id: uuid.UUID,
    reading_session_id: uuid.UUID,
    payload: ReadingCompleteRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> ReadingSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await complete_reading(
            session,
            child_id=child_id,
            reading_session_id=reading_session_id,
            evaluator_user_id=current_user.id,
            payload=payload,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{child_id}/reading-summary", response_model=ReadingSummaryResponse)
async def get_reading_summary(
    child_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> ReadingSummaryResponse:
    await get_authorized_child(session, current_user, child_id)
    return await reading_summary(session, child_id)
