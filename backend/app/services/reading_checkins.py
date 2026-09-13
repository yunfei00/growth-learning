"""Daily reading check-in aggregation and child-initiated help events."""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChineseCharacter,
    DailyReadingStatus,
    DailyReadingTask,
    KnowledgePoint,
    LearningActivityType,
    LearningRecord,
    LearningSession,
    ReadingSession,
    ReadingStatus,
    SessionStatus,
    StoryKnowledgePoint,
    StoryKnowledgeRole,
    StoryVersion,
)
from app.models.reading_checkin import ReadingHelpEvent
from app.schemas.reading_checkin import (
    ReadingCheckinDayResponse,
    ReadingCheckinSummaryResponse,
    ReadingHelpEventCreate,
    ReadingHelpEventResponse,
)
from app.schemas.story import ReadingCompleteRequest, ReadingSessionResponse
from app.services.daily_reading import mark_reading_completed
from app.services.story_analysis import extract_han
from app.services.story_pinyin import first_contextual_readings
from app.services.story_reading import reading_session_response


async def record_reading_help(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    reading_session_id: uuid.UUID,
    payload: ReadingHelpEventCreate,
) -> ReadingHelpEventResponse:
    reading = await session.scalar(
        select(ReadingSession).where(
            ReadingSession.id == reading_session_id,
            ReadingSession.child_id == child_id,
        )
    )
    if reading is None:
        raise LookupError("Reading session not found")

    version = await session.scalar(
        select(StoryVersion).where(StoryVersion.id == reading.story_version_id)
    )
    if version is None:
        raise LookupError("Story version not found")

    story_characters = set(extract_han("\n".join(version.paragraphs)))
    if payload.character not in story_characters:
        raise ValueError("Help character is not part of this story")

    knowledge_point_id = await session.scalar(
        select(KnowledgePoint.id)
        .join(ChineseCharacter)
        .where(ChineseCharacter.character == payload.character)
    )
    pinyin = first_contextual_readings(version.paragraphs).get(payload.character)
    event = ReadingHelpEvent(
        reading_session_id=reading.id,
        child_id=child_id,
        story_version_id=reading.story_version_id,
        knowledge_point_id=knowledge_point_id,
        character=payload.character,
        pinyin=pinyin,
        help_kind="character_tap",
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return ReadingHelpEventResponse(
        id=event.id,
        reading_session_id=event.reading_session_id,
        character=event.character,
        pinyin=event.pinyin,
        help_kind="character_tap",
        occurred_at=event.occurred_at,
    )


async def complete_independent_daily_reading(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    reading_session_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    payload: ReadingCompleteRequest,
    now: datetime | None = None,
) -> ReadingSessionResponse:
    """Finish a self-reading check-in without forcing comprehension questions.

    This deliberately mirrors the exposure semantics of the regular story
    completion path. The only difference is that optional comprehension answers
    do not gate the child's daily reading habit.
    """

    now = now or datetime.now(UTC)
    reading = await session.scalar(
        select(ReadingSession).where(
            ReadingSession.id == reading_session_id,
            ReadingSession.child_id == child_id,
        )
    )
    if reading is None:
        raise LookupError("Reading session not found")
    if reading.status == ReadingStatus.COMPLETED:
        return await reading_session_response(session, reading)
    if reading.reading_mode != "independent":
        raise ValueError("Only independent reading can use daily check-in completion")

    if reading.exposure_learning_session_id is None:
        target_ids = list(
            (
                await session.scalars(
                    select(StoryKnowledgePoint.knowledge_point_id).where(
                        StoryKnowledgePoint.story_version_id == reading.story_version_id,
                        StoryKnowledgePoint.role == StoryKnowledgeRole.TARGET,
                    )
                )
            ).all()
        )
        exposure_session = LearningSession(
            child_id=child_id,
            actor_user_id=evaluator_user_id,
            status=SessionStatus.COMPLETED,
            source="story_reading",
            started_at=reading.started_at,
            completed_at=now,
        )
        session.add(exposure_session)
        await session.flush()
        for point_id in target_ids:
            session.add(
                LearningRecord(
                    session_id=exposure_session.id,
                    child_id=child_id,
                    knowledge_point_id=point_id,
                    actor_user_id=evaluator_user_id,
                    activity_type=LearningActivityType.STORY_EXPOSURE,
                    source="story_reading",
                    learned_at=now,
                )
            )
        reading.exposure_learning_session_id = exposure_session.id
        await session.flush()

        from app.services.mastery import recompute_child_knowledge_state
        from app.services.review_planning import recompute_review_schedule

        for point_id in target_ids:
            await recompute_child_knowledge_state(session, child_id, point_id)
            await recompute_review_schedule(session, child_id, point_id)

    reading.status = ReadingStatus.COMPLETED
    reading.completed_at = now
    reading.duration_seconds = payload.duration_seconds
    reading.parent_note = payload.parent_note
    await mark_reading_completed(
        session,
        child_id,
        reading.story_version_id,
        reading.id,
        now,
    )
    await session.commit()
    return await reading_session_response(session, reading)


def _streaks(completed_dates: list[date], today: date) -> tuple[int, int]:
    unique_dates = sorted(set(completed_dates))
    if not unique_dates:
        return 0, 0

    longest = 1
    run = 1
    for previous, current in zip(unique_dates, unique_dates[1:], strict=False):
        if current == previous + timedelta(days=1):
            run += 1
            longest = max(longest, run)
        else:
            run = 1

    completed = set(unique_dates)
    cursor = today if today in completed else today - timedelta(days=1)
    current_streak = 0
    while cursor in completed:
        current_streak += 1
        cursor -= timedelta(days=1)
    return current_streak, longest


async def reading_checkin_summary(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    from_date: date,
    to_date: date,
    today: date,
) -> ReadingCheckinSummaryResponse:
    if from_date > to_date:
        raise ValueError("from must not be later than to")
    if (to_date - from_date).days > 370:
        raise ValueError("date range cannot exceed 371 days")

    rows = list(
        (
            await session.execute(
                select(DailyReadingTask, ReadingSession, StoryVersion)
                .outerjoin(
                    ReadingSession,
                    ReadingSession.id == DailyReadingTask.reading_session_id,
                )
                .outerjoin(
                    StoryVersion,
                    StoryVersion.id == DailyReadingTask.story_version_id,
                )
                .where(
                    DailyReadingTask.child_id == child_id,
                    DailyReadingTask.task_date >= from_date,
                    DailyReadingTask.task_date <= to_date,
                )
                .order_by(DailyReadingTask.task_date)
            )
        ).all()
    )

    days: list[ReadingCheckinDayResponse] = []
    total_duration = 0
    total_help_count = 0
    completed_days_in_range = 0

    for task, reading, version in rows:
        completed = task.status == DailyReadingStatus.COMPLETED
        if completed:
            completed_days_in_range += 1
        duration = reading.duration_seconds if reading else None
        if completed and duration:
            total_duration += duration

        help_characters: list[str] = []
        help_count = 0
        if reading is not None:
            help_events = list(
                (
                    await session.scalars(
                        select(ReadingHelpEvent)
                        .where(ReadingHelpEvent.reading_session_id == reading.id)
                        .order_by(ReadingHelpEvent.occurred_at)
                    )
                ).all()
            )
            help_count = len(help_events)
            help_characters = list(dict.fromkeys(item.character for item in help_events))
        if completed:
            total_help_count += help_count

        days.append(
            ReadingCheckinDayResponse(
                date=task.task_date,
                completed=completed,
                title=version.title if version else None,
                story_version_id=task.story_version_id,
                reading_session_id=task.reading_session_id,
                reading_mode=reading.reading_mode if reading else None,
                duration_seconds=duration,
                help_count=help_count,
                help_characters=help_characters,
            )
        )

    all_completed_dates = list(
        (
            await session.scalars(
                select(DailyReadingTask.task_date).where(
                    DailyReadingTask.child_id == child_id,
                    DailyReadingTask.status == DailyReadingStatus.COMPLETED,
                    DailyReadingTask.task_date <= today,
                )
            )
        ).all()
    )
    current_streak, longest_streak = _streaks(all_completed_dates, today)

    return ReadingCheckinSummaryResponse(
        from_date=from_date,
        to_date=to_date,
        today_completed=today in set(all_completed_dates),
        current_streak=current_streak,
        longest_streak=longest_streak,
        completed_days=completed_days_in_range,
        total_duration_seconds=total_duration,
        total_help_count=total_help_count,
        days=days,
    )
