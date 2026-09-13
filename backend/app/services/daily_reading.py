"""Persistence helpers for one real daily reading task.

Serialized reading takes priority for newly created daily tasks. Existing tasks
are preserved so an already-started day never jumps to a different story.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DailyLearningPlan,
    DailyReadingStatus,
    DailyReadingTask,
    ReadingSession,
    ReadingStatus,
    Story,
    StoryVersion,
)
from app.schemas.story import DailyReadingTaskResponse
from app.services.reading_series import episode_for_story_version, next_series_story_version


async def _legacy_unread_version(
    session: AsyncSession, child_id: uuid.UUID
) -> StoryVersion | None:
    return await session.scalar(
        select(StoryVersion)
        .join(Story, Story.id == StoryVersion.story_id)
        .outerjoin(
            ReadingSession,
            (ReadingSession.story_version_id == StoryVersion.id)
            & (ReadingSession.child_id == child_id),
        )
        .where(
            Story.child_id == child_id,
            Story.theme != "serialized_reading",
            (ReadingSession.id.is_(None)) | (ReadingSession.status != ReadingStatus.COMPLETED),
        )
        .order_by(StoryVersion.created_at.desc())
    )


async def ensure_daily_reading_task(
    session: AsyncSession, plan: DailyLearningPlan
) -> DailyReadingTask:
    task = await session.scalar(
        select(DailyReadingTask).where(DailyReadingTask.daily_plan_id == plan.id)
    )
    if task is not None:
        # Preserve a story already selected for this date. Only repair a
        # previously story-less task after the serialized pack is available.
        if task.story_version_id is None and task.status != DailyReadingStatus.COMPLETED:
            series_item = await next_series_story_version(session, plan.child_id)
            if series_item is not None:
                _, _, version = series_item
                task.story_version_id = version.id
                task.status = DailyReadingStatus.PENDING
        return task

    series_item = await next_series_story_version(session, plan.child_id)
    version = series_item[2] if series_item is not None else None
    if version is None:
        version = await _legacy_unread_version(session, plan.child_id)

    task = DailyReadingTask(
        daily_plan_id=plan.id,
        child_id=plan.child_id,
        task_date=plan.plan_date,
        story_version_id=version.id if version else None,
        status=DailyReadingStatus.PENDING if version else DailyReadingStatus.NEEDS_STORY,
    )
    session.add(task)
    await session.flush()
    return task


async def attach_story_to_today(
    session: AsyncSession, child_id: uuid.UUID, story_version_id: uuid.UUID
) -> None:
    plan = await session.scalar(
        select(DailyLearningPlan)
        .where(DailyLearningPlan.child_id == child_id)
        .order_by(DailyLearningPlan.plan_date.desc())
    )
    if plan is None:
        return
    task = await ensure_daily_reading_task(session, plan)
    if task.status == DailyReadingStatus.NEEDS_STORY:
        task.story_version_id = story_version_id
        task.status = DailyReadingStatus.PENDING


async def mark_reading_started(
    session: AsyncSession,
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    reading_session_id: uuid.UUID,
) -> None:
    task = await session.scalar(
        select(DailyReadingTask)
        .where(
            DailyReadingTask.child_id == child_id,
            DailyReadingTask.story_version_id == story_version_id,
        )
        .order_by(DailyReadingTask.task_date.desc())
    )
    if task and task.status != DailyReadingStatus.COMPLETED:
        task.reading_session_id = reading_session_id
        task.status = DailyReadingStatus.IN_PROGRESS


async def mark_reading_completed(
    session: AsyncSession,
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    reading_session_id: uuid.UUID,
    now: datetime,
) -> None:
    task = await session.scalar(
        select(DailyReadingTask)
        .where(
            DailyReadingTask.child_id == child_id,
            DailyReadingTask.story_version_id == story_version_id,
        )
        .order_by(DailyReadingTask.task_date.desc())
    )
    if task:
        task.reading_session_id = reading_session_id
        task.status = DailyReadingStatus.COMPLETED
        task.completed_at = now


async def daily_reading_response(
    session: AsyncSession, task: DailyReadingTask
) -> DailyReadingTaskResponse:
    title = None
    if task.story_version_id:
        series_episode = await episode_for_story_version(session, task.story_version_id)
        if series_episode is not None:
            series, episode = series_episode
            title = (
                f"{series.title} · 第{episode.episode_number}天/{series.total_episodes}天 · "
                f"{episode.title}"
            )
        else:
            title = await session.scalar(
                select(StoryVersion.title).where(StoryVersion.id == task.story_version_id)
            )
    return DailyReadingTaskResponse(
        status=task.status,
        story_version_id=task.story_version_id,
        reading_session_id=task.reading_session_id,
        title=title,
    )
