"""Child-private character learning, assessment, and mastery endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DbSession
from app.models import ChildKnowledgeState
from app.schemas.learning import (
    AssessmentSessionCreate,
    CharacterMasteryDetail,
    CharacterMasteryPage,
    CharacterMasteryState,
    CharacterMasterySummary,
    CharacterRecommendation,
    EvidenceSessionResponse,
    LearningSessionCreate,
    PriorityUpdate,
)
from app.services.authorization import get_authorized_child
from app.services.child_character_learning import (
    create_assessment_session,
    create_learning_session,
    get_character_mastery_detail,
    list_character_mastery,
    recommend_characters,
    summarize_character_mastery,
)
from app.services.mastery import recompute_child_knowledge_state

router = APIRouter(prefix="/children", tags=["character learning"])


@router.get("/{child_id}/characters/summary", response_model=CharacterMasterySummary)
async def get_character_summary(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> CharacterMasterySummary:
    await get_authorized_child(session, current_user, child_id)
    return await summarize_character_mastery(session, child_id)


@router.get("/{child_id}/characters/recommendations", response_model=list[CharacterRecommendation])
async def get_recommendations(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    mode: str = Query(default="new", pattern="^(new|assessment)$"),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[CharacterRecommendation]:
    await get_authorized_child(session, current_user, child_id)
    return await recommend_characters(session, child_id, mode=mode, limit=limit)


@router.get("/{child_id}/characters", response_model=CharacterMasteryPage)
async def get_character_states(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    search: str | None = Query(default=None, max_length=120),
    mastery_level: str | None = Query(
        default=None,
        pattern="^(unlearned|introduced|recognizing|proficient|stable)$",
    ),
    priority: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CharacterMasteryPage:
    await get_authorized_child(session, current_user, child_id)
    return await list_character_mastery(
        session,
        child_id,
        search=search,
        mastery_level=mastery_level,
        priority=priority,
        page=page,
        page_size=page_size,
    )


@router.get("/{child_id}/characters/{knowledge_point_id}", response_model=CharacterMasteryDetail)
async def get_character_state(
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> CharacterMasteryDetail:
    await get_authorized_child(session, current_user, child_id)
    detail = await get_character_mastery_detail(session, child_id, knowledge_point_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    return detail


@router.patch(
    "/{child_id}/characters/{knowledge_point_id}/priority",
    response_model=CharacterMasteryState,
)
async def update_character_priority(
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    payload: PriorityUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> CharacterMasteryState:
    await get_authorized_child(session, current_user, child_id, admin_required=True)
    detail = await get_character_mastery_detail(session, child_id, knowledge_point_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    state = await recompute_child_knowledge_state(
        session, child_id, knowledge_point_id, ensure_state=True
    )
    assert isinstance(state, ChildKnowledgeState)
    state.is_priority = payload.is_priority
    await session.commit()
    refreshed = await get_character_mastery_detail(session, child_id, knowledge_point_id)
    assert refreshed is not None
    return refreshed.state


@router.post(
    "/{child_id}/learning-sessions",
    response_model=EvidenceSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_learning_session(
    child_id: uuid.UUID,
    payload: LearningSessionCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> EvidenceSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await create_learning_session(session, child_id, current_user.id, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/{child_id}/assessment-sessions",
    response_model=EvidenceSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_assessment_session(
    child_id: uuid.UUID,
    payload: AssessmentSessionCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> EvidenceSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await create_assessment_session(session, child_id, current_user.id, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
