"""Unified child mode, growth tree, achievements, and family rewards API."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.models import FamilyRewardGoal
from app.schemas.experience import (
    AchievementRebuildResponse,
    AchievementSummaryResponse,
    ChildTodayResponse,
    GrowthTreeResponse,
    RewardGoalCreate,
    RewardGoalResponse,
    RewardGoalUpdate,
    RewardSettingsResponse,
    RewardSettingsUpdate,
)
from app.services.authorization import (
    get_authorized_child,
    require_family_admin,
    require_family_membership,
)
from app.services.child_experience import (
    achievement_summary,
    child_today,
    ensure_reward_settings,
    growth_tree,
    rebuild_child_achievements,
    reward_settings_response,
)

router = APIRouter(tags=["child experience"])


@router.get("/children/{child_id}/experience/today", response_model=ChildTodayResponse)
async def get_child_today(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> ChildTodayResponse:
    child, _ = await get_authorized_child(session, current_user, child_id)
    return await child_today(session, child, current_user)


@router.get("/children/{child_id}/growth-tree", response_model=GrowthTreeResponse)
async def get_growth_tree(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> GrowthTreeResponse:
    child, _ = await get_authorized_child(session, current_user, child_id)
    return await growth_tree(session, child)


@router.get("/children/{child_id}/achievements", response_model=AchievementSummaryResponse)
async def get_achievements(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> AchievementSummaryResponse:
    child, _ = await get_authorized_child(session, current_user, child_id)
    return await achievement_summary(session, child)


@router.post(
    "/children/{child_id}/achievements/rebuild",
    response_model=AchievementRebuildResponse,
)
async def rebuild_achievements(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> AchievementRebuildResponse:
    child, _ = await get_authorized_child(session, current_user, child_id)
    return await rebuild_child_achievements(session, child)


@router.get("/families/{family_id}/reward-settings", response_model=RewardSettingsResponse)
async def get_reward_settings(
    family_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> RewardSettingsResponse:
    await require_family_membership(session, current_user, family_id)
    return await reward_settings_response(session, family_id)


@router.patch("/families/{family_id}/reward-settings", response_model=RewardSettingsResponse)
async def patch_reward_settings(
    family_id: uuid.UUID,
    payload: RewardSettingsUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> RewardSettingsResponse:
    await require_family_admin(session, current_user, family_id)
    settings = await ensure_reward_settings(session, family_id)
    settings.stars_enabled = payload.stars_enabled
    await session.commit()
    return await reward_settings_response(session, family_id)


@router.post(
    "/families/{family_id}/reward-goals",
    response_model=RewardGoalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reward_goal(
    family_id: uuid.UUID,
    payload: RewardGoalCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> RewardGoalResponse:
    await require_family_admin(session, current_user, family_id)
    goal = FamilyRewardGoal(
        family_id=family_id,
        title=payload.title.strip(),
        required_stars=payload.required_stars,
        created_by_user_id=current_user.id,
    )
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return RewardGoalResponse.model_validate(goal)


@router.patch("/families/{family_id}/reward-goals/{goal_id}", response_model=RewardGoalResponse)
async def patch_reward_goal(
    family_id: uuid.UUID,
    goal_id: uuid.UUID,
    payload: RewardGoalUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> RewardGoalResponse:
    await require_family_admin(session, current_user, family_id)
    goal = await session.scalar(
        select(FamilyRewardGoal).where(
            FamilyRewardGoal.id == goal_id,
            FamilyRewardGoal.family_id == family_id,
        )
    )
    if goal is None:
        raise HTTPException(status_code=404, detail="Reward goal not found")
    values = payload.model_dump(exclude_none=True)
    for field, value in values.items():
        setattr(goal, field, value.strip() if field == "title" else value)
    await session.commit()
    return RewardGoalResponse.model_validate(goal)
