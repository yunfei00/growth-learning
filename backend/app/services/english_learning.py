"""English Foundation V1 learning, evidence, daily planning, and history."""

import secrets
import uuid
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentItem,
    AssessmentKind,
    AssessmentOutcome,
    AssessmentSession,
    ChildKnowledgeState,
    ChildLearningSettings,
    ChildReviewSchedule,
    DailyPlanStatus,
    EnglishAttemptMode,
    EnglishDailyPlan,
    EnglishDailyPlanItem,
    EnglishExerciseAttempt,
    EnglishItem,
    EnglishPracticeItem,
    KnowledgePoint,
    KnowledgeStatus,
    LearningActivityType,
    LearningRecord,
    LearningSession,
    PlanItemStatus,
    SessionStatus,
    User,
)
from app.schemas.english import (
    EnglishAttemptAnswer,
    EnglishAttemptAnswerResponse,
    EnglishAudioResponse,
    EnglishHistoryEvidence,
    EnglishHistoryItem,
    EnglishHistoryResponse,
    EnglishItemDetail,
    EnglishItemPage,
    EnglishItemSummary,
    EnglishNavigationItem,
    EnglishOverviewGroup,
    EnglishOverviewResponse,
    EnglishPracticeSummary,
    EnglishProblemResponse,
    EnglishSessionResponse,
    EnglishSessionStart,
    EnglishSpeakingObservationInput,
    EnglishSpeakingObservationResponse,
    EnglishTodayItem,
    EnglishTodayResponse,
    EnglishVisualResponse,
)
from app.services.english_audio import english_audio_provider
from app.services.english_catalog import (
    CATEGORY_LABELS,
    ENGLISH_CATALOG_VERSION,
    list_english_items,
)
from app.services.english_problem_generator import generate_english_problem
from app.services.english_visual import english_visual_provider
from app.services.mastery import mastery_policy_for_type, recompute_child_knowledge_state
from app.services.review_planning import recompute_review_schedule

ENGLISH_NEW_LIMIT = 3
ENGLISH_REVIEW_LIMIT = 6
ENGLISH_KIND_LABELS = {
    "word": "听懂词汇",
    "letter": "字母",
    "phonics": "自然拼读",
    "phrase": "简单短句",
}
ENGLISH_ALLOWED_DIMENSIONS = {
    "word": {"listening", "meaning", "speaking"},
    "letter": {
        "uppercase_recognition",
        "lowercase_recognition",
        "case_matching",
        "letter_name",
    },
    "phonics": {"sound_recognition", "grapheme_sound", "blending", "decoding"},
    "phrase": {"listening", "meaning", "expression"},
}


def _state_code(state: ChildKnowledgeState | None) -> str:
    if state is None:
        return "unlearned"
    return {
        "recognizing": "practicing",
        "unlearned": "unlearned",
        "introduced": "introduced",
        "proficient": "proficient",
        "stable": "stable",
    }.get(state.state_code or state.mastery_level, "practicing")


async def _practice_counts(session: AsyncSession) -> dict[uuid.UUID, int]:
    rows = (
        await session.execute(
            select(EnglishPracticeItem.knowledge_point_id, func.count())
            .where(EnglishPracticeItem.status == KnowledgeStatus.ACTIVE)
            .group_by(EnglishPracticeItem.knowledge_point_id)
        )
    ).all()
    return {point_id: int(count) for point_id, count in rows}


def english_item_summary(
    point: KnowledgePoint,
    item: EnglishItem,
    state: ChildKnowledgeState | None = None,
    *,
    practice_count: int = 0,
) -> EnglishItemSummary:
    audio = english_audio_provider.resolve(item)
    visual = english_visual_provider.resolve(item)
    state_code = _state_code(state)
    return EnglishItemSummary(
        knowledge_point_id=point.id,
        canonical_key=point.canonical_key,
        kind=item.kind,
        text=item.text,
        normalized_text=item.normalized_text,
        meaning_zh=item.meaning_zh,
        category=item.category,
        category_label=CATEGORY_LABELS.get(item.category, item.category),
        order_index=item.order_index,
        status=point.status,
        audio=EnglishAudioResponse(**asdict(audio)),
        visual=EnglishVisualResponse(**asdict(visual)),
        practice_count=practice_count,
        state_code=state_code,
        learned=state_code != "unlearned",
    )


async def child_english_items(
    session: AsyncSession,
    child_id: uuid.UUID,
    *,
    kind: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> EnglishItemPage:
    rows, total, pages = await list_english_items(
        session,
        kind=kind,
        category=category,
        page=page,
        page_size=page_size,
        public_only=True,
    )
    point_ids = [point.id for point, _ in rows]
    states = {
        value.knowledge_point_id: value
        for value in (
            await session.scalars(
                select(ChildKnowledgeState).where(
                    ChildKnowledgeState.child_id == child_id,
                    ChildKnowledgeState.knowledge_point_id.in_(point_ids),
                )
            )
        ).all()
    }
    counts = await _practice_counts(session)
    return EnglishItemPage(
        items=[
            english_item_summary(
                point, item, states.get(point.id), practice_count=counts.get(point.id, 0)
            )
            for point, item in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


def _mastery_explanation(state: ChildKnowledgeState | None) -> list[str]:
    if state is None:
        return ["还没有真实学习证据。", "先听声音并连接图片或动作即可开始。"]
    code = _state_code(state)
    explanations = {
        "introduced": ["已经接触过这个内容。"],
        "practicing": ["已有练习或测评证据，仍需要在不同日期继续听和理解。"],
        "proficient": ["核心维度已有跨日期独立成功证据。"],
        "stable": ["核心维度跨至少三天和七天保持独立成功。"],
        "unlearned": ["还没有真实学习证据。"],
    }
    result = list(explanations[code])
    if state.dimensions_json:
        result.append("会说、认读和拼读分别保存，不用一个总分覆盖所有能力。")
    return result


async def english_item_detail(
    session: AsyncSession,
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    *,
    include_archived: bool = False,
) -> EnglishItemDetail | None:
    row = (
        await session.execute(
            select(KnowledgePoint, EnglishItem)
            .join(EnglishItem, EnglishItem.knowledge_point_id == KnowledgePoint.id)
            .where(KnowledgePoint.id == knowledge_point_id)
        )
    ).one_or_none()
    if row is None:
        return None
    point, item = row
    if not include_archived and point.status != KnowledgeStatus.ACTIVE:
        return None
    state = None
    if child_id.int:
        state = await session.scalar(
            select(ChildKnowledgeState).where(
                ChildKnowledgeState.child_id == child_id,
                ChildKnowledgeState.knowledge_point_id == knowledge_point_id,
            )
        )
    practices = list(
        (
            await session.scalars(
                select(EnglishPracticeItem)
                .where(EnglishPracticeItem.knowledge_point_id == knowledge_point_id)
                .order_by(EnglishPracticeItem.order_index)
            )
        ).all()
    )
    navigation_rows = (
        await session.execute(
            select(KnowledgePoint, EnglishItem)
            .join(EnglishItem, EnglishItem.knowledge_point_id == KnowledgePoint.id)
            .where(
                KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                EnglishItem.kind == item.kind,
            )
            .order_by(EnglishItem.order_index)
        )
    ).all()
    position = next(
        (index for index, (nav_point, _) in enumerate(navigation_rows) if nav_point.id == point.id),
        0,
    )
    schedule = None
    if child_id.int:
        schedule = await session.scalar(
            select(ChildReviewSchedule).where(
                ChildReviewSchedule.child_id == child_id,
                ChildReviewSchedule.knowledge_point_id == knowledge_point_id,
            )
        )
    policy = mastery_policy_for_type(point.type)
    base = english_item_summary(point, item, state, practice_count=len(practices))
    return EnglishItemDetail(
        **base.model_dump(),
        child_hint_zh=item.child_hint_zh,
        parent_tip=item.parent_tip,
        example_text=item.example_text,
        example_meaning_zh=item.example_meaning_zh,
        image_key=item.image_key,
        visual_key=item.visual_key,
        visual_type=item.visual_type,
        audio_key=item.audio_key,
        metadata=item.metadata_json,
        catalog_version=item.catalog_version,
        practices=[
            EnglishPracticeSummary(
                id=value.id,
                template_key=value.template_key,
                practice_kind=value.practice_kind,
                generator_version=value.generator_version,
                status=value.status,
            )
            for value in practices
        ],
        position=position + 1,
        total=len(navigation_rows),
        previous=(
            EnglishNavigationItem(
                knowledge_point_id=navigation_rows[position - 1][0].id,
                text=navigation_rows[position - 1][1].text,
            )
            if position > 0
            else None
        ),
        next=(
            EnglishNavigationItem(
                knowledge_point_id=navigation_rows[position + 1][0].id,
                text=navigation_rows[position + 1][1].text,
            )
            if position + 1 < len(navigation_rows)
            else None
        ),
        policy_key=policy.key if policy else "unsupported",
        dimensions=state.dimensions_json if state else {},
        mastery_explanation=_mastery_explanation(state),
        last_learning_at=state.last_learning_at if state else None,
        last_assessed_at=state.last_assessed_at if state else None,
        next_review_at=schedule.next_review_at if schedule else None,
    )


async def english_overview(session: AsyncSession, child_id: uuid.UUID) -> EnglishOverviewResponse:
    rows = (
        await session.execute(
            select(KnowledgePoint, EnglishItem)
            .join(EnglishItem, EnglishItem.knowledge_point_id == KnowledgePoint.id)
            .where(KnowledgePoint.status == KnowledgeStatus.ACTIVE)
            .order_by(EnglishItem.order_index)
        )
    ).all()
    states = {
        value.knowledge_point_id: value
        for value in (
            await session.scalars(
                select(ChildKnowledgeState).where(ChildKnowledgeState.child_id == child_id)
            )
        ).all()
    }
    groups: list[EnglishOverviewGroup] = []
    for kind in ("word", "letter", "phonics", "phrase"):
        kind_rows = [(point, item) for point, item in rows if item.kind == kind]
        kind_states = [_state_code(states.get(point.id)) for point, _ in kind_rows]
        learned = sum(value != "unlearned" for value in kind_states)
        proficient = sum(value in {"proficient", "stable"} for value in kind_states)
        stable = sum(value == "stable" for value in kind_states)
        group_state = "unlearned"
        if learned:
            group_state = "introduced"
        if learned >= max(1, len(kind_states) // 3):
            group_state = "practicing"
        if proficient >= max(1, (len(kind_states) + 1) // 2):
            group_state = "proficient"
        if kind_states and stable == len(kind_states):
            group_state = "stable"
        groups.append(
            EnglishOverviewGroup(
                kind=kind,
                label=ENGLISH_KIND_LABELS[kind],
                total=len(kind_rows),
                learned=learned,
                proficient=proficient,
                stable=stable,
                state_code=group_state,
            )
        )
    word_points = {point.id for point, item in rows if item.kind == "word"}
    speaking_observed = sum(
        bool((states.get(point_id).dimensions_json if states.get(point_id) else {}).get("speaking"))
        for point_id in word_points
    )
    all_states = [_state_code(states.get(point.id)) for point, _ in rows]
    by_kind = {group.kind: group for group in groups}
    return EnglishOverviewResponse(
        child_id=child_id,
        catalog_version=ENGLISH_CATALOG_VERSION,
        total=len(rows),
        learned=sum(value != "unlearned" for value in all_states),
        stable=sum(value == "stable" for value in all_states),
        understood_words=by_kind["word"].proficient,
        stable_words=by_kind["word"].stable,
        speaking_observed=speaking_observed,
        letters_learned=by_kind["letter"].learned,
        letters_total=by_kind["letter"].total,
        phonics_practicing=by_kind["phonics"].learned,
        phrases_learned=by_kind["phrase"].learned,
        groups=groups,
    )


async def start_english_session(
    session: AsyncSession,
    child_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    payload: EnglishSessionStart,
    *,
    now: datetime | None = None,
) -> EnglishSessionResponse:
    now = now or datetime.now(UTC)
    point = await session.get(KnowledgePoint, payload.knowledge_point_id)
    item = await session.get(EnglishItem, payload.knowledge_point_id)
    if point is None or item is None or point.status != KnowledgeStatus.ACTIVE:
        raise LookupError("English item not found")
    practices = list(
        (
            await session.scalars(
                select(EnglishPracticeItem)
                .where(
                    EnglishPracticeItem.knowledge_point_id == payload.knowledge_point_id,
                    EnglishPracticeItem.status == KnowledgeStatus.ACTIVE,
                )
                .order_by(EnglishPracticeItem.order_index)
            )
        ).all()
    )
    if not practices:
        raise LookupError("English item has no active practice")
    requested_dimension = payload.dimension
    if requested_dimension and requested_dimension not in ENGLISH_ALLOWED_DIMENSIONS[item.kind]:
        raise ValueError(f"Dimension {requested_dimension} is not valid for {item.kind}")
    candidates = [
        practice
        for practice in practices
        if not requested_dimension
        or str(practice.config_json.get("dimension")) == requested_dimension
    ] or practices
    base_seed = payload.seed if payload.seed is not None else secrets.randbelow(2_147_000_000)
    practice = candidates[base_seed % len(candidates)]
    dimension = requested_dimension or str(practice.config_json.get("dimension", "listening"))
    if payload.mode == EnglishAttemptMode.PRACTICE:
        canonical_session: LearningSession | AssessmentSession = LearningSession(
            child_id=child_id,
            actor_user_id=actor_user_id,
            status=SessionStatus.IN_PROGRESS,
            source="english_practice",
            started_at=now,
        )
    else:
        canonical_session = AssessmentSession(
            child_id=child_id,
            evaluator_user_id=actor_user_id,
            status=SessionStatus.IN_PROGRESS,
            source="english_item_check",
            assessment_kind=(
                AssessmentKind.LISTENING_CHECK
                if item.kind in {"word", "phrase"}
                else AssessmentKind.PRACTICE_CHECK
            ),
            started_at=now,
        )
    session.add(canonical_session)
    await session.flush()
    for index in range(payload.exercise_count):
        problem_seed = (base_seed + index * 7919) % 2_147_483_000
        generated = await generate_english_problem(session, practice, problem_seed)
        session.add(
            EnglishExerciseAttempt(
                child_id=child_id,
                knowledge_point_id=point.id,
                session_id=canonical_session.id,
                mode=payload.mode,
                practice_item_id=practice.id,
                template_key=generated.template_key,
                practice_kind=generated.practice_kind,
                generator_version=generated.generator_version,
                seed=generated.seed,
                prompt_snapshot=generated.prompt,
                options_snapshot=generated.options,
                expected_answer=generated.expected_answer,
                evidence_dimension=dimension,
                started_at=now,
                actor_user_id=actor_user_id,
                evaluator_user_id=(
                    actor_user_id if payload.mode == EnglishAttemptMode.ASSESSMENT else None
                ),
            )
        )
    await session.commit()
    response = await english_session_response(session, child_id, canonical_session.id)
    assert response is not None
    return response


async def english_session_response(
    session: AsyncSession, child_id: uuid.UUID, session_id: uuid.UUID
) -> EnglishSessionResponse | None:
    attempts = list(
        (
            await session.scalars(
                select(EnglishExerciseAttempt)
                .where(
                    EnglishExerciseAttempt.child_id == child_id,
                    EnglishExerciseAttempt.session_id == session_id,
                )
                .order_by(EnglishExerciseAttempt.created_at, EnglishExerciseAttempt.id)
            )
        ).all()
    )
    if not attempts:
        return None
    item = await session.get(EnglishItem, attempts[0].knowledge_point_id)
    assert item is not None
    completed_count = sum(value.attempt_count > 0 for value in attempts)
    return EnglishSessionResponse(
        session_id=session_id,
        child_id=child_id,
        knowledge_point_id=item.knowledge_point_id,
        item_text=item.text,
        item_kind=item.kind,
        mode=attempts[0].mode,
        dimension=attempts[0].evidence_dimension,
        problems=[
            EnglishProblemResponse(
                attempt_id=value.id,
                template_key=value.template_key,
                generator_version=value.generator_version,
                seed=value.seed,
                practice_kind=value.practice_kind,
                dimension=value.evidence_dimension,
                prompt=value.prompt_snapshot,
                options=value.options_snapshot,
                answered=value.attempt_count > 0,
            )
            for value in attempts
        ],
        completed_count=completed_count,
        total_count=len(attempts),
        completed=completed_count == len(attempts),
    )


async def _update_english_daily_progress(
    session: AsyncSession,
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    *,
    now: datetime,
) -> None:
    settings = await session.scalar(
        select(ChildLearningSettings).where(ChildLearningSettings.child_id == child_id)
    )
    timezone_name = settings.timezone if settings else "Asia/Shanghai"
    plan_date = now.astimezone(ZoneInfo(timezone_name)).date()
    plan = await session.scalar(
        select(EnglishDailyPlan).where(
            EnglishDailyPlan.child_id == child_id,
            EnglishDailyPlan.plan_date == plan_date,
        )
    )
    if plan is None:
        return
    item = await session.scalar(
        select(EnglishDailyPlanItem).where(
            EnglishDailyPlanItem.english_daily_plan_id == plan.id,
            EnglishDailyPlanItem.knowledge_point_id == knowledge_point_id,
        )
    )
    if item is not None and item.status != PlanItemStatus.COMPLETED:
        item.status = PlanItemStatus.COMPLETED
        item.completed_at = now
    items = list(
        (
            await session.scalars(
                select(EnglishDailyPlanItem).where(
                    EnglishDailyPlanItem.english_daily_plan_id == plan.id
                )
            )
        ).all()
    )
    plan.completed_count = sum(value.status == PlanItemStatus.COMPLETED for value in items)
    if items and plan.completed_count == len(items):
        plan.status = DailyPlanStatus.COMPLETED
    elif plan.completed_count:
        plan.status = DailyPlanStatus.IN_PROGRESS


async def answer_english_attempt(
    session: AsyncSession,
    child_id: uuid.UUID,
    session_id: uuid.UUID,
    attempt_id: uuid.UUID,
    _actor_user_id: uuid.UUID,
    payload: EnglishAttemptAnswer,
    *,
    now: datetime | None = None,
) -> EnglishAttemptAnswerResponse:
    now = now or datetime.now(UTC)
    attempt = await session.scalar(
        select(EnglishExerciseAttempt).where(
            EnglishExerciseAttempt.id == attempt_id,
            EnglishExerciseAttempt.session_id == session_id,
            EnglishExerciseAttempt.child_id == child_id,
        )
    )
    if attempt is None:
        raise LookupError("English attempt not found")
    if attempt.mode == EnglishAttemptMode.ASSESSMENT and attempt.attempt_count:
        raise RuntimeError("Assessment first answer is already preserved")
    if attempt.attempt_count == 0:
        attempt.first_answer = payload.submitted_answer
    attempt.submitted_answer = payload.submitted_answer
    attempt.attempt_count += 1
    attempt.hint_used = attempt.hint_used or payload.hint_used
    attempt.audio_replay_count += payload.audio_replays
    attempt.answered_at = now
    attempt.response_time_ms = payload.response_time_ms
    is_correct = payload.submitted_answer == attempt.expected_answer
    first_correct = attempt.first_answer == attempt.expected_answer
    if is_correct and attempt.attempt_count == 1 and not attempt.hint_used:
        attempt.outcome = AssessmentOutcome.CORRECT
        feedback = "听出来啦！"
    elif is_correct and attempt.hint_used:
        attempt.outcome = AssessmentOutcome.HINTED_CORRECT
        feedback = "在提示下找到了，下次再听听看。"
    elif is_correct:
        attempt.outcome = AssessmentOutcome.UNCERTAIN
        feedback = "找到了！第一次的回答也已经保留下来。"
    else:
        attempt.outcome = AssessmentOutcome.INCORRECT
        feedback = "再听一次，慢慢找一找。"
    await session.flush()
    attempts = list(
        (
            await session.scalars(
                select(EnglishExerciseAttempt).where(
                    EnglishExerciseAttempt.child_id == child_id,
                    EnglishExerciseAttempt.session_id == session_id,
                )
            )
        ).all()
    )
    completed = all(value.attempt_count > 0 for value in attempts)
    mastery_state: str | None = None
    if completed:
        if attempt.mode == EnglishAttemptMode.PRACTICE:
            learning_session = await session.get(LearningSession, session_id)
            if learning_session is None:
                raise RuntimeError("English learning session not found")
            existing = await session.scalar(
                select(LearningRecord.id).where(
                    LearningRecord.session_id == session_id,
                    LearningRecord.knowledge_point_id == attempt.knowledge_point_id,
                )
            )
            if existing is None:
                independent = all(
                    value.outcome == AssessmentOutcome.CORRECT and not value.hint_used
                    for value in attempts
                )
                session.add(
                    LearningRecord(
                        session_id=session_id,
                        child_id=child_id,
                        knowledge_point_id=attempt.knowledge_point_id,
                        actor_user_id=learning_session.actor_user_id,
                        activity_type=(
                            LearningActivityType.INDEPENDENT_PRACTICE
                            if independent
                            else LearningActivityType.GUIDED_PRACTICE
                        ),
                        source="english_practice",
                        learned_at=now,
                    )
                )
            learning_session.status = SessionStatus.COMPLETED
            learning_session.completed_at = now
        else:
            assessment_session = await session.get(AssessmentSession, session_id)
            if assessment_session is None:
                raise RuntimeError("English assessment session not found")
            existing = await session.scalar(
                select(AssessmentItem.id).where(
                    AssessmentItem.session_id == session_id,
                    AssessmentItem.knowledge_point_id == attempt.knowledge_point_id,
                )
            )
            if existing is None:
                correct_count = sum(
                    value.outcome == AssessmentOutcome.CORRECT for value in attempts
                )
                hinted_count = sum(
                    value.outcome == AssessmentOutcome.HINTED_CORRECT for value in attempts
                )
                if correct_count == len(attempts):
                    aggregate = AssessmentOutcome.CORRECT
                elif correct_count + hinted_count == len(attempts) and hinted_count:
                    aggregate = AssessmentOutcome.HINTED_CORRECT
                elif correct_count + hinted_count >= (len(attempts) + 1) // 2:
                    aggregate = AssessmentOutcome.UNCERTAIN
                else:
                    aggregate = AssessmentOutcome.INCORRECT
                response_times = [
                    value.response_time_ms
                    for value in attempts
                    if value.response_time_ms is not None
                ]
                session.add(
                    AssessmentItem(
                        session_id=session_id,
                        child_id=child_id,
                        knowledge_point_id=attempt.knowledge_point_id,
                        evaluator_user_id=assessment_session.evaluator_user_id,
                        outcome=aggregate,
                        response_time_ms=(
                            round(sum(response_times) / len(response_times))
                            if response_times
                            else None
                        ),
                        hint_used=any(value.hint_used for value in attempts),
                        skill_dimension=attempt.evidence_dimension,
                        evidence_metadata={
                            "problem_count": len(attempts),
                            "first_answer_correct_count": sum(
                                value.first_answer == value.expected_answer for value in attempts
                            ),
                            "practice_kind": attempt.practice_kind,
                            "template_keys": sorted({value.template_key for value in attempts}),
                            "audio_replay_count": sum(
                                value.audio_replay_count for value in attempts
                            ),
                            "replay_is_hint": False,
                            "attempt_ids": [str(value.id) for value in attempts],
                        },
                        assessed_at=now,
                    )
                )
            assessment_session.status = SessionStatus.COMPLETED
            assessment_session.completed_at = now
        await session.flush()
        state = await recompute_child_knowledge_state(
            session, child_id, attempt.knowledge_point_id, ensure_state=True
        )
        await recompute_review_schedule(session, child_id, attempt.knowledge_point_id)
        await _update_english_daily_progress(session, child_id, attempt.knowledge_point_id, now=now)
        mastery_state = _state_code(state)
    await session.commit()
    return EnglishAttemptAnswerResponse(
        attempt_id=attempt.id,
        outcome=attempt.outcome,
        first_answer_correct=first_correct,
        attempt_count=attempt.attempt_count,
        hint_used=attempt.hint_used,
        audio_replay_count=attempt.audio_replay_count,
        feedback=feedback,
        session_completed=completed,
        mastery_state=mastery_state,
    )


async def record_speaking_observation(
    session: AsyncSession,
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    payload: EnglishSpeakingObservationInput,
    *,
    now: datetime | None = None,
) -> EnglishSpeakingObservationResponse:
    now = now or datetime.now(UTC)
    item = await session.get(EnglishItem, knowledge_point_id)
    if item is None or item.kind not in {"word", "phrase"}:
        raise LookupError("Speaking observation target not found")
    dimension = "expression" if item.kind == "phrase" else "speaking"
    outcome = {
        "can_say": AssessmentOutcome.CORRECT,
        "willing_to_repeat": AssessmentOutcome.HINTED_CORRECT,
        "needs_prompt": AssessmentOutcome.UNCERTAIN,
        "not_yet": AssessmentOutcome.INCORRECT,
    }[payload.observation]
    assessment = AssessmentSession(
        child_id=child_id,
        evaluator_user_id=actor_user_id,
        status=SessionStatus.COMPLETED,
        source="english_speaking_observation",
        assessment_kind=AssessmentKind.ORAL_CHECK,
        started_at=now,
        completed_at=now,
    )
    session.add(assessment)
    await session.flush()
    evidence = AssessmentItem(
        session_id=assessment.id,
        child_id=child_id,
        knowledge_point_id=knowledge_point_id,
        evaluator_user_id=actor_user_id,
        outcome=outcome,
        hint_used=outcome != AssessmentOutcome.CORRECT,
        skill_dimension=dimension,
        evidence_metadata={
            "observation": payload.observation,
            "automatic_speech_score": False,
        },
        assessed_at=now,
    )
    session.add(evidence)
    await session.flush()
    state = await recompute_child_knowledge_state(
        session, child_id, knowledge_point_id, ensure_state=True
    )
    await recompute_review_schedule(session, child_id, knowledge_point_id)
    await session.commit()
    return EnglishSpeakingObservationResponse(
        assessment_item_id=evidence.id,
        dimension=dimension,
        outcome=outcome,
        mastery_state=_state_code(state),
    )


async def get_or_create_english_today(
    session: AsyncSession,
    child_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> EnglishTodayResponse | None:
    now = now or datetime.now(UTC)
    settings = await session.scalar(
        select(ChildLearningSettings).where(ChildLearningSettings.child_id == child_id)
    )
    timezone_name = settings.timezone if settings else "Asia/Shanghai"
    plan_date = now.astimezone(ZoneInfo(timezone_name)).date()
    plan = await session.scalar(
        select(EnglishDailyPlan).where(
            EnglishDailyPlan.child_id == child_id,
            EnglishDailyPlan.plan_date == plan_date,
        )
    )
    if plan is not None:
        return await _english_today_response(session, plan)
    catalog_exists = await session.scalar(select(EnglishItem.knowledge_point_id).limit(1))
    if catalog_exists is None:
        return None
    due = list(
        (
            await session.scalars(
                select(EnglishItem)
                .join(
                    ChildReviewSchedule,
                    ChildReviewSchedule.knowledge_point_id == EnglishItem.knowledge_point_id,
                )
                .join(KnowledgePoint, KnowledgePoint.id == EnglishItem.knowledge_point_id)
                .where(
                    ChildReviewSchedule.child_id == child_id,
                    ChildReviewSchedule.next_review_at <= now,
                    ChildReviewSchedule.algorithm_version == "english-review-v1",
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                )
                .order_by(ChildReviewSchedule.next_review_at, EnglishItem.order_index)
                .limit(ENGLISH_REVIEW_LIMIT)
            )
        ).all()
    )
    new_items = list(
        (
            await session.scalars(
                select(EnglishItem)
                .join(KnowledgePoint, KnowledgePoint.id == EnglishItem.knowledge_point_id)
                .outerjoin(
                    ChildKnowledgeState,
                    (ChildKnowledgeState.knowledge_point_id == EnglishItem.knowledge_point_id)
                    & (ChildKnowledgeState.child_id == child_id),
                )
                .where(
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChildKnowledgeState.id.is_(None),
                    EnglishItem.knowledge_point_id.not_in(
                        [value.knowledge_point_id for value in due]
                    ),
                )
                .order_by(EnglishItem.order_index)
                .limit(ENGLISH_NEW_LIMIT)
            )
        ).all()
    )
    selected = [*new_items, *due]
    plan = EnglishDailyPlan(
        child_id=child_id,
        plan_date=plan_date,
        timezone=timezone_name,
        new_count=len(new_items),
        review_count=len(due),
        completed_count=0,
        status=DailyPlanStatus.PENDING,
        algorithm_version="english-plan-v1",
    )
    session.add(plan)
    await session.flush()
    new_ids = {value.knowledge_point_id for value in new_items}
    for position, item in enumerate(selected):
        session.add(
            EnglishDailyPlanItem(
                english_daily_plan_id=plan.id,
                knowledge_point_id=item.knowledge_point_id,
                item_kind="new" if item.knowledge_point_id in new_ids else "review",
                status=PlanItemStatus.PENDING,
                position=position,
                exercise_count=3,
            )
        )
    await session.flush()
    return await _english_today_response(session, plan)


async def _english_today_response(
    session: AsyncSession, plan: EnglishDailyPlan
) -> EnglishTodayResponse:
    rows = (
        await session.execute(
            select(EnglishDailyPlanItem, KnowledgePoint, EnglishItem, ChildKnowledgeState)
            .join(KnowledgePoint, KnowledgePoint.id == EnglishDailyPlanItem.knowledge_point_id)
            .join(EnglishItem, EnglishItem.knowledge_point_id == KnowledgePoint.id)
            .outerjoin(
                ChildKnowledgeState,
                (ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id)
                & (ChildKnowledgeState.child_id == plan.child_id),
            )
            .where(EnglishDailyPlanItem.english_daily_plan_id == plan.id)
            .order_by(EnglishDailyPlanItem.position)
        )
    ).all()
    counts = await _practice_counts(session)
    items = [
        EnglishTodayItem(
            **english_item_summary(
                point,
                item,
                state,
                practice_count=counts.get(point.id, 0),
            ).model_dump(),
            item_kind=plan_item.item_kind,
            exercise_count=plan_item.exercise_count,
            completed=plan_item.status == PlanItemStatus.COMPLETED,
        )
        for plan_item, point, item, state in rows
    ]
    return EnglishTodayResponse(
        plan_id=plan.id,
        child_id=plan.child_id,
        plan_date=plan.plan_date,
        items=items,
        completed_count=plan.completed_count,
        target_count=len(items),
        status=plan.status,
        estimated_minutes=min(10, max(5, len(items) + 2)) if items else 0,
    )


async def english_history(
    session: AsyncSession, child_id: uuid.UUID, *, limit: int = 30
) -> EnglishHistoryResponse:
    attempts = (
        await session.execute(
            select(EnglishExerciseAttempt, EnglishItem, User)
            .join(
                EnglishItem,
                EnglishItem.knowledge_point_id == EnglishExerciseAttempt.knowledge_point_id,
            )
            .join(User, User.id == EnglishExerciseAttempt.actor_user_id)
            .where(
                EnglishExerciseAttempt.child_id == child_id,
                EnglishExerciseAttempt.attempt_count > 0,
            )
            .order_by(EnglishExerciseAttempt.started_at.desc())
            .limit(limit * 8)
        )
    ).all()
    grouped: dict[uuid.UUID, list[tuple[EnglishExerciseAttempt, EnglishItem, User]]] = defaultdict(
        list
    )
    for attempt, item, user in attempts:
        grouped[attempt.session_id].append((attempt, item, user))
    history: list[EnglishHistoryItem] = []
    for session_id, rows in list(grouped.items())[:limit]:
        first_attempt, _, actor = rows[0]
        by_point: dict[uuid.UUID, list[EnglishExerciseAttempt]] = defaultdict(list)
        item_by_point: dict[uuid.UUID, EnglishItem] = {}
        for attempt, item, _ in rows:
            by_point[attempt.knowledge_point_id].append(attempt)
            item_by_point[item.knowledge_point_id] = item
        evidence = []
        for point_id, point_attempts in by_point.items():
            item = item_by_point[point_id]
            evidence.append(
                EnglishHistoryEvidence(
                    knowledge_point_id=point_id,
                    text=item.text,
                    kind=item.kind,
                    dimension=point_attempts[0].evidence_dimension,
                    problem_count=len(point_attempts),
                    correct=sum(
                        value.outcome == AssessmentOutcome.CORRECT for value in point_attempts
                    ),
                    hinted_correct=sum(
                        value.outcome == AssessmentOutcome.HINTED_CORRECT
                        for value in point_attempts
                    ),
                    uncertain=sum(
                        value.outcome == AssessmentOutcome.UNCERTAIN for value in point_attempts
                    ),
                    incorrect=sum(
                        value.outcome == AssessmentOutcome.INCORRECT for value in point_attempts
                    ),
                    speaking_observations=0,
                )
            )
        history.append(
            EnglishHistoryItem(
                session_id=session_id,
                mode=first_attempt.mode,
                actor_display_name=actor.display_name,
                occurred_at=first_attempt.started_at,
                evidence=evidence,
            )
        )
    observations = (
        await session.execute(
            select(AssessmentItem, AssessmentSession, EnglishItem, User)
            .join(AssessmentSession, AssessmentSession.id == AssessmentItem.session_id)
            .join(EnglishItem, EnglishItem.knowledge_point_id == AssessmentItem.knowledge_point_id)
            .join(User, User.id == AssessmentItem.evaluator_user_id)
            .where(
                AssessmentItem.child_id == child_id,
                AssessmentSession.source == "english_speaking_observation",
            )
            .order_by(AssessmentItem.assessed_at.desc())
            .limit(limit)
        )
    ).all()
    for evidence, assessment, item, actor in observations:
        history.append(
            EnglishHistoryItem(
                session_id=assessment.id,
                mode="observation",
                actor_display_name=actor.display_name,
                occurred_at=evidence.assessed_at,
                evidence=[
                    EnglishHistoryEvidence(
                        knowledge_point_id=item.knowledge_point_id,
                        text=item.text,
                        kind=item.kind,
                        dimension=evidence.skill_dimension or "speaking",
                        problem_count=0,
                        correct=int(evidence.outcome == AssessmentOutcome.CORRECT),
                        hinted_correct=int(evidence.outcome == AssessmentOutcome.HINTED_CORRECT),
                        uncertain=int(evidence.outcome == AssessmentOutcome.UNCERTAIN),
                        incorrect=int(evidence.outcome == AssessmentOutcome.INCORRECT),
                        speaking_observations=1,
                    )
                ],
            )
        )
    history.sort(key=lambda value: value.occurred_at, reverse=True)
    return EnglishHistoryResponse(child_id=child_id, items=history[:limit])
