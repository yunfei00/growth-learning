"""Mastery-aware story generation and household-private reading routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.dependencies import CurrentUser, DbSession
from app.integrations.ai.base import AIProvider
from app.integrations.ai.factory import build_ai_provider
from app.schemas.story import (
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


StoryAIProvider = Annotated[AIProvider, Depends(get_story_ai_provider)]


def _provider_config(request: Request) -> tuple[bool, str, str]:
    settings = request.app.state.settings
    configured = bool(
        settings.ai_provider != "disabled"
        and settings.ai_api_key.get_secret_value()
        and settings.ai_model
    )
    return configured, settings.ai_provider, settings.ai_model


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


@router.get("/{child_id}/stories", response_model=StoryPageResponse)
async def get_storybook(
    child_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
) -> StoryPageResponse:
    await get_authorized_child(session, current_user, child_id)
    return await list_storybook(session, child_id, page=page, page_size=page_size)


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
