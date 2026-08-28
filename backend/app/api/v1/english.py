"""Authenticated English Foundation learning and system-admin maintenance."""

import mimetypes
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.dependencies import CurrentUser, DbSession, require_system_admin
from app.integrations.object_storage import PrivateObjectStorage, build_private_object_storage
from app.models import EnglishItem, KnowledgePoint
from app.schemas.english import (
    EnglishAttemptAnswer,
    EnglishAttemptAnswerResponse,
    EnglishHistoryResponse,
    EnglishImportResponse,
    EnglishItemDetail,
    EnglishItemPage,
    EnglishItemUpdate,
    EnglishOverviewResponse,
    EnglishSessionResponse,
    EnglishSessionStart,
    EnglishSpeakingObservationInput,
    EnglishSpeakingObservationResponse,
    EnglishTodayResponse,
)
from app.services.authorization import get_authorized_child
from app.services.english_audio import english_audio_provider
from app.services.english_catalog import import_english_foundation, list_english_items
from app.services.english_learning import (
    _practice_counts,
    answer_english_attempt,
    child_english_items,
    english_history,
    english_item_detail,
    english_item_summary,
    english_overview,
    english_session_response,
    get_or_create_english_today,
    record_speaking_observation,
    start_english_session,
)

router = APIRouter(tags=["english"])
admin_router = APIRouter(
    prefix="/admin/english",
    tags=["system administration", "english"],
    dependencies=[Depends(require_system_admin)],
)


def get_english_storage(request: Request) -> PrivateObjectStorage:
    return build_private_object_storage(request.app.state.settings)


EnglishStorage = Annotated[PrivateObjectStorage, Depends(get_english_storage)]


@router.get("/english/items", response_model=EnglishItemPage)
async def list_public_english_items(
    _: CurrentUser,
    session: DbSession,
    kind: str | None = Query(default=None, pattern="^(letter|word|phonics|phrase)$"),
    category: str | None = Query(default=None, max_length=60),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=250),
) -> EnglishItemPage:
    rows, total, pages = await list_english_items(
        session,
        kind=kind,
        category=category,
        page=page,
        page_size=page_size,
        public_only=True,
    )
    counts = await _practice_counts(session)
    return EnglishItemPage(
        items=[
            english_item_summary(point, item, practice_count=counts.get(point.id, 0))
            for point, item in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/english/items/{knowledge_point_id}/audio", response_class=Response)
async def stream_english_audio(
    knowledge_point_id: uuid.UUID,
    _: CurrentUser,
    session: DbSession,
    storage: EnglishStorage,
) -> Response:
    item = await session.get(EnglishItem, knowledge_point_id)
    point = await session.get(KnowledgePoint, knowledge_point_id)
    if item is None or point is None or point.status != "active":
        raise HTTPException(status_code=404, detail="English item not found")
    try:
        object_key = english_audio_provider.curated_object_key(item, knowledge_point_id)
        content = await storage.read(object_key)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    media_type = mimetypes.guess_type(object_key)[0] or "audio/mpeg"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/children/{child_id}/english/items", response_model=EnglishItemPage)
async def list_child_english_items(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    kind: str | None = Query(default=None, pattern="^(letter|word|phonics|phrase)$"),
    category: str | None = Query(default=None, max_length=60),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=250, ge=1, le=250),
) -> EnglishItemPage:
    await get_authorized_child(session, current_user, child_id)
    return await child_english_items(
        session,
        child_id,
        kind=kind,
        category=category,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/children/{child_id}/english/items/{knowledge_point_id}",
    response_model=EnglishItemDetail,
)
async def get_child_english_item(
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> EnglishItemDetail:
    await get_authorized_child(session, current_user, child_id)
    detail = await english_item_detail(session, child_id, knowledge_point_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="English item not found")
    return detail


@router.get("/children/{child_id}/english/overview", response_model=EnglishOverviewResponse)
async def get_child_english_overview(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> EnglishOverviewResponse:
    await get_authorized_child(session, current_user, child_id)
    return await english_overview(session, child_id)


@router.get("/children/{child_id}/english/today", response_model=EnglishTodayResponse | None)
async def get_child_english_today(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> EnglishTodayResponse | None:
    await get_authorized_child(session, current_user, child_id)
    response = await get_or_create_english_today(session, child_id)
    await session.commit()
    return response


@router.get("/children/{child_id}/english/history", response_model=EnglishHistoryResponse)
async def get_child_english_history(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=30, ge=1, le=100),
) -> EnglishHistoryResponse:
    await get_authorized_child(session, current_user, child_id)
    return await english_history(session, child_id, limit=limit)


@router.post(
    "/children/{child_id}/english/sessions",
    response_model=EnglishSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_english_session(
    child_id: uuid.UUID,
    payload: EnglishSessionStart,
    current_user: CurrentUser,
    session: DbSession,
) -> EnglishSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await start_english_session(session, child_id, current_user.id, payload)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get(
    "/children/{child_id}/english/sessions/{session_id}",
    response_model=EnglishSessionResponse,
)
async def get_english_session(
    child_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> EnglishSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    response = await english_session_response(session, child_id, session_id)
    if response is None:
        raise HTTPException(status_code=404, detail="English session not found")
    return response


@router.post(
    "/children/{child_id}/english/sessions/{session_id}/attempts/{attempt_id}/answer",
    response_model=EnglishAttemptAnswerResponse,
)
async def submit_english_answer(
    child_id: uuid.UUID,
    session_id: uuid.UUID,
    attempt_id: uuid.UUID,
    payload: EnglishAttemptAnswer,
    current_user: CurrentUser,
    session: DbSession,
) -> EnglishAttemptAnswerResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await answer_english_attempt(
            session,
            child_id,
            session_id,
            attempt_id,
            current_user.id,
            payload,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/children/{child_id}/english/items/{knowledge_point_id}/speaking-observations",
    response_model=EnglishSpeakingObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_english_speaking_observation(
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    payload: EnglishSpeakingObservationInput,
    current_user: CurrentUser,
    session: DbSession,
) -> EnglishSpeakingObservationResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await record_speaking_observation(
            session, child_id, knowledge_point_id, current_user.id, payload
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@admin_router.get("", response_model=EnglishItemPage)
async def admin_list_english(
    session: DbSession,
    kind: str | None = Query(default=None, pattern="^(letter|word|phonics|phrase)$"),
    category: str | None = Query(default=None, max_length=60),
    item_status: str | None = Query(default=None, alias="status", pattern="^(active|archived)$"),
    audio_status: str | None = Query(default=None, pattern="^(curated|tts|phonics_missing)$"),
    visual_status: str | None = Query(default=None, pattern="^(static|fallback|missing)$"),
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=250),
) -> EnglishItemPage:
    rows, total, pages = await list_english_items(
        session,
        kind=kind,
        category=category,
        status=item_status,
        audio_status=audio_status,
        visual_status=visual_status,
        search=search,
        page=page,
        page_size=page_size,
    )
    counts = await _practice_counts(session)
    return EnglishItemPage(
        items=[
            english_item_summary(point, item, practice_count=counts.get(point.id, 0))
            for point, item in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@admin_router.post(
    "/import-foundation",
    response_model=EnglishImportResponse,
    status_code=status.HTTP_200_OK,
)
async def admin_import_english(session: DbSession) -> EnglishImportResponse:
    result = await import_english_foundation(session)
    return EnglishImportResponse(**result.__dict__)


@admin_router.get("/{knowledge_point_id}", response_model=EnglishItemDetail)
async def admin_get_english_item(
    knowledge_point_id: uuid.UUID, session: DbSession
) -> EnglishItemDetail:
    detail = await english_item_detail(
        session, uuid.UUID(int=0), knowledge_point_id, include_archived=True
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="English item not found")
    return detail


@admin_router.patch("/{knowledge_point_id}", response_model=EnglishItemDetail)
async def admin_update_english_item(
    knowledge_point_id: uuid.UUID,
    payload: EnglishItemUpdate,
    session: DbSession,
) -> EnglishItemDetail:
    point = await session.get(KnowledgePoint, knowledge_point_id)
    item = await session.get(EnglishItem, knowledge_point_id)
    if point is None or item is None:
        raise HTTPException(status_code=404, detail="English item not found")
    values = payload.model_dump(exclude_unset=True)
    new_status = values.pop("status", None)
    if new_status is not None:
        point.status = new_status
    for name, value in values.items():
        setattr(item, name, value.strip() if isinstance(value, str) else value)
    await session.commit()
    detail = await english_item_detail(
        session, uuid.UUID(int=0), knowledge_point_id, include_archived=True
    )
    assert detail is not None
    return detail
