"""Authenticated Math Foundation learning and system-admin catalog maintenance."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DbSession, require_system_admin
from app.models import KnowledgePoint, MathSkill
from app.schemas.math import (
    MathAttemptAnswer,
    MathAttemptAnswerResponse,
    MathHistoryResponse,
    MathImportResponse,
    MathOfflineObservationInput,
    MathOfflineObservationResponse,
    MathOverviewResponse,
    MathSessionResponse,
    MathSessionStart,
    MathSkillDetail,
    MathSkillPage,
    MathSkillUpdate,
    MathTodayResponse,
)
from app.services.authorization import get_authorized_child
from app.services.math_catalog import import_math_foundation, list_math_skills
from app.services.math_learning import (
    _template_counts,
    answer_math_attempt,
    child_math_skills,
    get_or_create_math_today,
    math_history,
    math_overview,
    math_session_response,
    math_skill_detail,
    math_skill_summary,
    record_math_offline_observation,
    start_math_session,
)

router = APIRouter(tags=["math"])
admin_router = APIRouter(
    prefix="/admin/math",
    tags=["system administration", "math"],
    dependencies=[Depends(require_system_admin)],
)


@router.get("/math/skills", response_model=MathSkillPage)
async def list_public_math_skills(
    _: CurrentUser,
    session: DbSession,
    domain: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
) -> MathSkillPage:
    rows, total, pages = await list_math_skills(
        session, domain=domain, page=page, page_size=page_size, public_only=True
    )
    counts = await _template_counts(session)
    return MathSkillPage(
        items=[
            math_skill_summary(point, skill, template_count=counts.get(point.id, 0))
            for point, skill in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/children/{child_id}/math/skills", response_model=MathSkillPage)
async def list_child_math_skills(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    domain: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
) -> MathSkillPage:
    await get_authorized_child(session, current_user, child_id)
    return await child_math_skills(session, child_id, domain=domain, page=page, page_size=page_size)


@router.get(
    "/children/{child_id}/math/skills/{knowledge_point_id}",
    response_model=MathSkillDetail,
)
async def get_child_math_skill(
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> MathSkillDetail:
    await get_authorized_child(session, current_user, child_id)
    detail = await math_skill_detail(session, child_id, knowledge_point_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Math skill not found")
    return detail


@router.get("/children/{child_id}/math/overview", response_model=MathOverviewResponse)
async def get_child_math_overview(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> MathOverviewResponse:
    await get_authorized_child(session, current_user, child_id)
    return await math_overview(session, child_id)


@router.post(
    "/children/{child_id}/math/skills/{knowledge_point_id}/offline-observations",
    response_model=MathOfflineObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_math_offline_observation(
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    payload: MathOfflineObservationInput,
    current_user: CurrentUser,
    session: DbSession,
) -> MathOfflineObservationResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await record_math_offline_observation(
            session, child_id, knowledge_point_id, current_user.id, payload
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/children/{child_id}/math/today", response_model=MathTodayResponse | None)
async def get_child_math_today(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> MathTodayResponse | None:
    await get_authorized_child(session, current_user, child_id)
    response = await get_or_create_math_today(session, child_id)
    await session.commit()
    return response


@router.get("/children/{child_id}/math/history", response_model=MathHistoryResponse)
async def get_child_math_history(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=30, ge=1, le=100),
) -> MathHistoryResponse:
    await get_authorized_child(session, current_user, child_id)
    return await math_history(session, child_id, limit=limit)


@router.post(
    "/children/{child_id}/math/sessions",
    response_model=MathSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_math_session(
    child_id: uuid.UUID,
    payload: MathSessionStart,
    current_user: CurrentUser,
    session: DbSession,
) -> MathSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await start_math_session(session, child_id, current_user.id, payload)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/children/{child_id}/math/sessions/{session_id}", response_model=MathSessionResponse)
async def get_math_session(
    child_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> MathSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    response = await math_session_response(session, child_id, session_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Math session not found")
    return response


@router.post(
    "/children/{child_id}/math/sessions/{session_id}/attempts/{attempt_id}/answer",
    response_model=MathAttemptAnswerResponse,
)
async def submit_math_answer(
    child_id: uuid.UUID,
    session_id: uuid.UUID,
    attempt_id: uuid.UUID,
    payload: MathAttemptAnswer,
    current_user: CurrentUser,
    session: DbSession,
) -> MathAttemptAnswerResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await answer_math_attempt(
            session, child_id, session_id, attempt_id, current_user.id, payload
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@admin_router.get("", response_model=MathSkillPage)
async def admin_list_math(
    session: DbSession,
    domain: str | None = Query(default=None, max_length=40),
    item_status: str | None = Query(default=None, alias="status", pattern="^(active|archived)$"),
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> MathSkillPage:
    rows, total, pages = await list_math_skills(
        session,
        domain=domain,
        status=item_status,
        search=search,
        page=page,
        page_size=page_size,
    )
    counts = await _template_counts(session)
    return MathSkillPage(
        items=[
            math_skill_summary(point, skill, template_count=counts.get(point.id, 0))
            for point, skill in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@admin_router.post(
    "/import-foundation", response_model=MathImportResponse, status_code=status.HTTP_200_OK
)
async def admin_import_math(session: DbSession) -> MathImportResponse:
    result = await import_math_foundation(session)
    return MathImportResponse(**result.__dict__)


@admin_router.get("/{knowledge_point_id}", response_model=MathSkillDetail)
async def admin_get_math_skill(
    knowledge_point_id: uuid.UUID, session: DbSession
) -> MathSkillDetail:
    detail = await math_skill_detail(
        session, uuid.UUID(int=0), knowledge_point_id, include_archived=True
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Math skill not found")
    return detail


@admin_router.patch("/{knowledge_point_id}", response_model=MathSkillDetail)
async def admin_update_math_skill(
    knowledge_point_id: uuid.UUID, payload: MathSkillUpdate, session: DbSession
) -> MathSkillDetail:
    point = await session.get(KnowledgePoint, knowledge_point_id)
    skill = await session.get(MathSkill, knowledge_point_id)
    if point is None or skill is None:
        raise HTTPException(status_code=404, detail="Math skill not found")
    values = payload.model_dump(exclude_unset=True)
    new_status = values.pop("status", None)
    if new_status is not None:
        point.status = new_status
    for name, value in values.items():
        setattr(skill, name, value.strip() if isinstance(value, str) else value)
        if name == "title":
            point.title = value.strip()
    await session.commit()
    detail = await math_skill_detail(
        session, uuid.UUID(int=0), knowledge_point_id, include_archived=True
    )
    assert detail is not None
    return detail
