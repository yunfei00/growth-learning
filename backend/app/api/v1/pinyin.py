"""Authenticated Pinyin catalog, child learning projections, and admin maintenance."""

import mimetypes
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.dependencies import CurrentUser, DbSession, require_system_admin
from app.integrations.object_storage import PrivateObjectStorage, build_private_object_storage
from app.models import KnowledgePoint, PinyinItem
from app.schemas.pinyin import (
    PinyinHistoryResponse,
    PinyinImportResponse,
    PinyinItemDetail,
    PinyinItemPage,
    PinyinItemUpdate,
    PinyinOverviewResponse,
    PinyinPracticePage,
    PinyinTodayResponse,
)
from app.services.authorization import get_authorized_child
from app.services.pinyin_audio import pinyin_audio_provider
from app.services.pinyin_catalog import import_pinyin_foundation, list_pinyin_items
from app.services.pinyin_learning import (
    child_pinyin_items,
    get_or_create_pinyin_today,
    pinyin_history,
    pinyin_item_detail,
    pinyin_item_summary,
    pinyin_overview,
    pinyin_practice_page,
)

router = APIRouter(tags=["pinyin"])
admin_router = APIRouter(
    prefix="/admin/pinyin",
    tags=["system administration", "pinyin"],
    dependencies=[Depends(require_system_admin)],
)


def get_pinyin_storage(request: Request) -> PrivateObjectStorage:
    return build_private_object_storage(request.app.state.settings)


PinyinStorage = Annotated[PrivateObjectStorage, Depends(get_pinyin_storage)]


@router.get("/pinyin/items", response_model=PinyinItemPage)
async def list_enabled_pinyin(
    _: CurrentUser,
    session: DbSession,
    kind: str | None = Query(default=None, pattern="^(initial|final|tone|whole)$"),
    subcategory: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
) -> PinyinItemPage:
    rows, total, pages = await list_pinyin_items(
        session,
        kind=kind,
        subcategory=subcategory,
        page=page,
        page_size=page_size,
        public_only=True,
    )
    return PinyinItemPage(
        items=[pinyin_item_summary(point, item) for point, item in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/children/{child_id}/pinyin/items", response_model=PinyinItemPage)
async def list_child_pinyin(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    kind: str | None = Query(default=None, pattern="^(initial|final|tone|whole)$"),
    subcategory: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
) -> PinyinItemPage:
    await get_authorized_child(session, current_user, child_id)
    return await child_pinyin_items(
        session,
        child_id,
        kind=kind,
        subcategory=subcategory,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/children/{child_id}/pinyin/items/{knowledge_point_id}",
    response_model=PinyinItemDetail,
)
async def get_child_pinyin_item(
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> PinyinItemDetail:
    await get_authorized_child(session, current_user, child_id)
    detail = await pinyin_item_detail(session, child_id, knowledge_point_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Pinyin item not found")
    return detail


@router.get("/children/{child_id}/pinyin/overview", response_model=PinyinOverviewResponse)
async def get_child_pinyin_overview(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> PinyinOverviewResponse:
    await get_authorized_child(session, current_user, child_id)
    return await pinyin_overview(session, child_id)


@router.get("/children/{child_id}/pinyin/today", response_model=PinyinTodayResponse | None)
async def get_child_pinyin_today(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> PinyinTodayResponse | None:
    await get_authorized_child(session, current_user, child_id)
    response = await get_or_create_pinyin_today(session, child_id)
    await session.commit()
    return response


@router.get("/children/{child_id}/pinyin/history", response_model=PinyinHistoryResponse)
async def get_child_pinyin_history(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=30, ge=1, le=100),
) -> PinyinHistoryResponse:
    await get_authorized_child(session, current_user, child_id)
    return await pinyin_history(session, child_id, limit=limit)


@router.get("/pinyin/practices", response_model=PinyinPracticePage)
async def list_pinyin_practices(_: CurrentUser, session: DbSession) -> PinyinPracticePage:
    return await pinyin_practice_page(session)


@router.get("/pinyin/items/{knowledge_point_id}/audio", response_class=Response)
async def stream_pinyin_audio(
    knowledge_point_id: uuid.UUID,
    _: CurrentUser,
    session: DbSession,
    storage: PinyinStorage,
) -> Response:
    item = await session.get(PinyinItem, knowledge_point_id)
    point = await session.get(KnowledgePoint, knowledge_point_id)
    if item is None or point is None or point.status != "active":
        raise HTTPException(status_code=404, detail="Pinyin item not found")
    try:
        object_key = pinyin_audio_provider.curated_object_key(item, knowledge_point_id)
        content = await storage.read(object_key)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    media_type = mimetypes.guess_type(object_key)[0] or "audio/mpeg"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )


@admin_router.get("", response_model=PinyinItemPage)
async def admin_list_pinyin(
    session: DbSession,
    kind: str | None = Query(default=None, pattern="^(initial|final|tone|whole)$"),
    item_status: str | None = Query(default=None, alias="status", pattern="^(active|archived)$"),
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PinyinItemPage:
    rows, total, pages = await list_pinyin_items(
        session,
        kind=kind,
        status=item_status,
        search=search,
        page=page,
        page_size=page_size,
    )
    return PinyinItemPage(
        items=[pinyin_item_summary(point, item) for point, item in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@admin_router.post(
    "/import-foundation",
    response_model=PinyinImportResponse,
    status_code=status.HTTP_200_OK,
)
async def admin_import_pinyin(session: DbSession) -> PinyinImportResponse:
    result = await import_pinyin_foundation(session)
    return PinyinImportResponse(**result.__dict__)


@admin_router.get("/{knowledge_point_id}", response_model=PinyinItemDetail)
async def admin_get_pinyin(knowledge_point_id: uuid.UUID, session: DbSession) -> PinyinItemDetail:
    detail = await pinyin_item_detail(
        session, uuid.UUID(int=0), knowledge_point_id, include_archived=True
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Pinyin item not found")
    return detail


@admin_router.patch("/{knowledge_point_id}", response_model=PinyinItemDetail)
async def admin_update_pinyin(
    knowledge_point_id: uuid.UUID,
    payload: PinyinItemUpdate,
    session: DbSession,
) -> PinyinItemDetail:
    point = await session.get(KnowledgePoint, knowledge_point_id)
    item = await session.get(PinyinItem, knowledge_point_id)
    if point is None or item is None:
        raise HTTPException(status_code=404, detail="Pinyin item not found")
    values = payload.model_dump(exclude_unset=True)
    new_status = values.pop("status", None)
    if new_status is not None:
        point.status = new_status
    for field_name, value in values.items():
        setattr(item, field_name, value.strip() or None if isinstance(value, str) else value)
    await session.commit()
    detail = await pinyin_item_detail(
        session, uuid.UUID(int=0), knowledge_point_id, include_archived=True
    )
    assert detail is not None
    return detail
