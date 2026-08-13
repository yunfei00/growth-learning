"""Private storybook reads, resumable sessions, comprehension, and exposure evidence."""

import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChineseCharacter,
    KnowledgePoint,
    LearningActivityType,
    LearningRecord,
    LearningSession,
    ReadingAnswer,
    ReadingAnswerOutcome,
    ReadingQuestion,
    ReadingSession,
    ReadingStatus,
    SessionStatus,
    Story,
    StoryKnowledgePoint,
    StoryKnowledgeRole,
    StoryVersion,
)
from app.schemas.story import (
    CharacterGlossaryResponse,
    ReadingAnswerResponse,
    ReadingAnswersSubmit,
    ReadingCompleteRequest,
    ReadingQuestionResponse,
    ReadingSessionResponse,
    ReadingSessionStart,
    ReadingSummaryResponse,
    StoryListItemResponse,
    StoryPageResponse,
    StoryVersionResponse,
)
from app.services.daily_reading import mark_reading_completed, mark_reading_started


async def get_private_story_version(
    session: AsyncSession, child_id: uuid.UUID, version_id: uuid.UUID
) -> tuple[Story, StoryVersion] | None:
    return (
        await session.execute(
            select(Story, StoryVersion)
            .join(StoryVersion, StoryVersion.story_id == Story.id)
            .where(Story.child_id == child_id, StoryVersion.id == version_id)
        )
    ).one_or_none()


async def story_version_response(
    session: AsyncSession, child_id: uuid.UUID, version: StoryVersion
) -> StoryVersionResponse:
    story = await session.scalar(
        select(Story).where(Story.id == version.story_id, Story.child_id == child_id)
    )
    if story is None:
        raise LookupError("Story version not found")
    questions = list(
        (
            await session.scalars(
                select(ReadingQuestion)
                .where(ReadingQuestion.story_version_id == version.id)
                .order_by(ReadingQuestion.position)
            )
        ).all()
    )
    glossary_rows = list(
        (
            await session.execute(
                select(KnowledgePoint.id, ChineseCharacter)
                .join(ChineseCharacter)
                .join(
                    StoryKnowledgePoint,
                    StoryKnowledgePoint.knowledge_point_id == KnowledgePoint.id,
                )
                .where(StoryKnowledgePoint.story_version_id == version.id)
                .order_by(ChineseCharacter.character)
            )
        ).all()
    )
    return StoryVersionResponse(
        id=version.id,
        story_id=story.id,
        source_experiment_session_id=version.source_experiment_session_id,
        version_number=version.version_number,
        title=version.title,
        paragraphs=version.paragraphs,
        summary=version.summary,
        theme=version.theme,
        custom_theme=version.custom_theme,
        difficulty=version.difficulty,
        requested_known_coverage=version.requested_known_coverage,
        actual_strong_known_coverage=version.actual_strong_known_coverage,
        actual_usable_known_coverage=version.actual_usable_known_coverage,
        actual_target_coverage=version.actual_target_coverage,
        actual_unexpected_coverage=version.actual_unexpected_coverage,
        unique_known_coverage=version.unique_known_coverage,
        total_han_occurrences=version.total_han_occurrences,
        unique_han_count=version.unique_han_count,
        unexpected_characters=version.unexpected_characters,
        target_characters=version.target_characters,
        snapshot_at=version.snapshot_at,
        coverage_policy_version=version.coverage_policy_version,
        analyzer_version=version.analyzer_version,
        prompt_version=version.prompt_version,
        provider=version.provider,
        model=version.model,
        questions=[
            ReadingQuestionResponse(
                id=question.id,
                position=question.position,
                question=question.question,
                options=question.options,
            )
            for question in questions
        ],
        glossary=[
            CharacterGlossaryResponse(
                knowledge_point_id=point_id,
                character=character.character,
                pinyin=character.pinyin,
                simple_meaning=character.simple_meaning,
                common_words=character.common_words,
            )
            for point_id, character in glossary_rows
        ],
        created_at=version.created_at,
    )


async def list_storybook(
    session: AsyncSession,
    child_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    difficulty: str | None = None,
) -> StoryPageResponse:
    query = (
        select(Story, StoryVersion)
        .join(StoryVersion, StoryVersion.story_id == Story.id)
        .where(Story.child_id == child_id)
    )
    if search:
        query = query.where(StoryVersion.title.ilike(f"%{search.strip()}%"))
    if difficulty:
        query = query.where(StoryVersion.difficulty == difficulty)
    rows = list((await session.execute(query.order_by(StoryVersion.created_at.desc()))).all())
    total = len(rows)
    selected = rows[(page - 1) * page_size : page * page_size]
    items: list[StoryListItemResponse] = []
    for story, version in selected:
        reading = await session.scalar(
            select(ReadingSession).where(
                ReadingSession.child_id == child_id,
                ReadingSession.story_version_id == version.id,
            )
        )
        question_count = int(
            await session.scalar(
                select(func.count())
                .select_from(ReadingQuestion)
                .where(ReadingQuestion.story_version_id == version.id)
            )
            or 0
        )
        answer_count = (
            int(
                await session.scalar(
                    select(func.count())
                    .select_from(ReadingAnswer)
                    .where(ReadingAnswer.reading_session_id == reading.id)
                )
                or 0
            )
            if reading
            else 0
        )
        items.append(
            StoryListItemResponse(
                story_id=story.id,
                story_version_id=version.id,
                title=version.title,
                theme=version.theme,
                difficulty=version.difficulty,
                actual_known_coverage=version.actual_usable_known_coverage,
                target_characters=version.target_characters,
                generated_at=version.created_at,
                reading_status=reading.status if reading else None,
                reading_mode=reading.reading_mode if reading else None,
                comprehension_answered=answer_count,
                comprehension_total=question_count,
            )
        )
    return StoryPageResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


async def reading_session_response(
    session: AsyncSession, reading: ReadingSession
) -> ReadingSessionResponse:
    answers = list(
        (
            await session.scalars(
                select(ReadingAnswer)
                .where(ReadingAnswer.reading_session_id == reading.id)
                .order_by(ReadingAnswer.answered_at)
            )
        ).all()
    )
    exposure_count = (
        int(
            await session.scalar(
                select(func.count())
                .select_from(LearningRecord)
                .where(LearningRecord.session_id == reading.exposure_learning_session_id)
            )
            or 0
        )
        if reading.exposure_learning_session_id
        else 0
    )
    return ReadingSessionResponse(
        id=reading.id,
        child_id=reading.child_id,
        story_version_id=reading.story_version_id,
        reading_mode=reading.reading_mode,
        status=reading.status,
        started_at=reading.started_at,
        completed_at=reading.completed_at,
        duration_seconds=reading.duration_seconds,
        parent_note=reading.parent_note,
        answers=[ReadingAnswerResponse.model_validate(answer) for answer in answers],
        story_exposure_count=exposure_count,
    )


async def start_or_resume_reading(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    story_version_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    payload: ReadingSessionStart,
) -> ReadingSessionResponse:
    if await get_private_story_version(session, child_id, story_version_id) is None:
        raise LookupError("Story version not found")
    reading = await session.scalar(
        select(ReadingSession).where(
            ReadingSession.child_id == child_id,
            ReadingSession.story_version_id == story_version_id,
        )
    )
    if reading is None:
        reading = ReadingSession(
            child_id=child_id,
            story_version_id=story_version_id,
            evaluator_user_id=evaluator_user_id,
            reading_mode=payload.reading_mode,
        )
        session.add(reading)
        await session.flush()
    elif reading.status == ReadingStatus.ABANDONED:
        reading.status = ReadingStatus.IN_PROGRESS
        reading.reading_mode = payload.reading_mode
    await mark_reading_started(session, child_id, story_version_id, reading.id)
    await session.commit()
    return await reading_session_response(session, reading)


async def submit_reading_answers(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    reading_session_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    payload: ReadingAnswersSubmit,
) -> ReadingSessionResponse:
    reading = await session.scalar(
        select(ReadingSession).where(
            ReadingSession.id == reading_session_id,
            ReadingSession.child_id == child_id,
        )
    )
    if reading is None:
        raise LookupError("Reading session not found")
    if reading.status != ReadingStatus.IN_PROGRESS:
        raise RuntimeError("Reading session is no longer in progress")
    questions = {
        question.id: question
        for question in (
            await session.scalars(
                select(ReadingQuestion).where(
                    ReadingQuestion.story_version_id == reading.story_version_id,
                    ReadingQuestion.id.in_([answer.question_id for answer in payload.answers]),
                )
            )
        ).all()
    }
    if len(questions) != len(payload.answers):
        raise ValueError("Answer contains a question outside this story version")
    existing = set(
        (
            await session.scalars(
                select(ReadingAnswer.question_id).where(
                    ReadingAnswer.reading_session_id == reading.id,
                    ReadingAnswer.question_id.in_(questions),
                )
            )
        ).all()
    )
    if existing:
        raise RuntimeError("One or more questions already have preserved answers")
    for item in payload.answers:
        question = questions[item.question_id]
        if item.selected_option_index >= len(question.options):
            raise ValueError("Selected option does not exist")
        if item.outcome in (ReadingAnswerOutcome.WITH_HELP, ReadingAnswerOutcome.PARTIAL):
            outcome = item.outcome
        else:
            outcome = (
                ReadingAnswerOutcome.CORRECT
                if item.selected_option_index == question.correct_option_index
                else ReadingAnswerOutcome.INCORRECT
            )
        session.add(
            ReadingAnswer(
                reading_session_id=reading.id,
                question_id=question.id,
                evaluator_user_id=evaluator_user_id,
                selected_option_index=item.selected_option_index,
                outcome=outcome,
            )
        )
    await session.commit()
    return await reading_session_response(session, reading)


async def complete_reading(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    reading_session_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    payload: ReadingCompleteRequest,
    now: datetime | None = None,
) -> ReadingSessionResponse:
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
    question_count = int(
        await session.scalar(
            select(func.count())
            .select_from(ReadingQuestion)
            .where(ReadingQuestion.story_version_id == reading.story_version_id)
        )
        or 0
    )
    answer_count = int(
        await session.scalar(
            select(func.count())
            .select_from(ReadingAnswer)
            .where(ReadingAnswer.reading_session_id == reading.id)
        )
        or 0
    )
    if answer_count < question_count:
        raise ValueError("请完成阅读理解题后再结束阅读")

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
    await mark_reading_completed(session, child_id, reading.story_version_id, reading.id, now)
    await session.commit()
    return await reading_session_response(session, reading)


async def reading_summary(session: AsyncSession, child_id: uuid.UUID) -> ReadingSummaryResponse:
    since = datetime.now(UTC) - timedelta(days=7)
    completed = list(
        (
            await session.scalars(
                select(ReadingSession).where(
                    ReadingSession.child_id == child_id,
                    ReadingSession.status == ReadingStatus.COMPLETED,
                    ReadingSession.completed_at >= since,
                )
            )
        ).all()
    )
    ids = [item.id for item in completed]
    outcomes: list[str] = []
    if ids:
        outcomes = list(
            (
                await session.scalars(
                    select(ReadingAnswer.outcome).where(ReadingAnswer.reading_session_id.in_(ids))
                )
            ).all()
        )
    exposure_count = int(
        await session.scalar(
            select(func.count())
            .select_from(LearningRecord)
            .where(
                LearningRecord.child_id == child_id,
                LearningRecord.activity_type == LearningActivityType.STORY_EXPOSURE,
            )
        )
        or 0
    )
    correct = outcomes.count(ReadingAnswerOutcome.CORRECT)
    return ReadingSummaryResponse(
        stories_read_this_week=len(completed),
        independent_this_week=sum(item.reading_mode == "independent" for item in completed),
        with_help_this_week=sum(item.reading_mode == "with_help" for item in completed),
        comprehension_correct=correct,
        comprehension_answered=len(outcomes),
        comprehension_message=(
            f"近7天答对 {correct} / {len(outcomes)}"
            if len(outcomes) >= 3
            else "数据不足，完成更多阅读理解后再显示趋势"
        ),
        target_exposure_count=exposure_count,
    )
