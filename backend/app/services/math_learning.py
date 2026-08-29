"""Child Math Foundation projections, sessions, evidence, daily plan, and history."""

import secrets
import uuid
from collections import defaultdict
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
    KnowledgePoint,
    KnowledgeRelation,
    KnowledgeStatus,
    LearningActivityType,
    LearningRecord,
    LearningSession,
    MathAttemptMode,
    MathDailyPlan,
    MathDailyPlanItem,
    MathExerciseAttempt,
    MathProblemTemplate,
    MathSkill,
    PlanItemStatus,
    RelationType,
    SessionStatus,
    User,
)
from app.schemas.math import (
    MathAttemptAnswer,
    MathAttemptAnswerResponse,
    MathHistoryResponse,
    MathHistorySession,
    MathHistorySkill,
    MathNavigationItem,
    MathOfflineObservationInput,
    MathOfflineObservationResponse,
    MathOverviewGroup,
    MathOverviewResponse,
    MathProblemResponse,
    MathSessionResponse,
    MathSessionStart,
    MathSkillDetail,
    MathSkillPage,
    MathSkillSummary,
    MathTemplateSummary,
    MathTodayItem,
    MathTodayResponse,
)
from app.services.mastery import MATH_POLICY_KEY, recompute_child_knowledge_state
from app.services.math_catalog import MATH_CATALOG_VERSION
from app.services.math_problem_generator import math_problem_generators
from app.services.review_planning import MATH_REVIEW_ALGORITHM_VERSION, recompute_review_schedule

MATH_DOMAIN_LABELS = {
    "classification": "分类与配对",
    "quantity": "数量与数感",
    "number_symbol": "数字与数序",
    "comparison": "大小比较",
    "sequence": "数序",
    "composition": "分解组合",
    "operation": "加减理解",
    "pattern": "规律",
    "geometry": "图形",
    "spatial": "空间",
    "measurement": "简单测量",
}
MATH_NEW_LIMIT = 1
MATH_REVIEW_LIMIT = 2


def _state_code(state: ChildKnowledgeState | None) -> str:
    if state is None:
        return "unlearned"
    return state.state_code or {
        "unlearned": "unlearned",
        "introduced": "introduced",
        "recognizing": "practicing",
        "proficient": "proficient",
        "stable": "stable",
    }.get(state.mastery_level, "unlearned")


async def _template_counts(session: AsyncSession) -> dict[uuid.UUID, int]:
    rows = (
        await session.execute(
            select(MathProblemTemplate.knowledge_point_id, func.count())
            .where(MathProblemTemplate.status == KnowledgeStatus.ACTIVE)
            .group_by(MathProblemTemplate.knowledge_point_id)
        )
    ).all()
    return {point_id: count for point_id, count in rows}


def math_skill_summary(
    point: KnowledgePoint,
    skill: MathSkill,
    state: ChildKnowledgeState | None = None,
    *,
    template_count: int = 0,
) -> MathSkillSummary:
    state_code = _state_code(state)
    return MathSkillSummary(
        knowledge_point_id=point.id,
        canonical_key=point.canonical_key,
        domain=skill.domain,
        skill_code=skill.skill_code,
        title=skill.title,
        difficulty_level=skill.difficulty_level,
        order_index=skill.order_index,
        status=point.status,
        representation_types=list(skill.representation_types),
        template_count=template_count,
        state_code=state_code,
        learned=state_code != "unlearned",
    )


async def child_math_skills(
    session: AsyncSession,
    child_id: uuid.UUID,
    *,
    domain: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> MathSkillPage:
    filters = [KnowledgePoint.status == KnowledgeStatus.ACTIVE]
    if domain:
        filters.append(MathSkill.domain == domain)
    total = int(
        await session.scalar(
            select(func.count()).select_from(MathSkill).join(KnowledgePoint).where(*filters)
        )
        or 0
    )
    rows = (
        await session.execute(
            select(KnowledgePoint, MathSkill, ChildKnowledgeState)
            .join(MathSkill, MathSkill.knowledge_point_id == KnowledgePoint.id)
            .outerjoin(
                ChildKnowledgeState,
                (ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id)
                & (ChildKnowledgeState.child_id == child_id),
            )
            .where(*filters)
            .order_by(MathSkill.order_index)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    counts = await _template_counts(session)
    return MathSkillPage(
        items=[
            math_skill_summary(point, skill, state, template_count=counts.get(point.id, 0))
            for point, skill, state in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, (total + page_size - 1) // page_size),
    )


def _mastery_explanation(state: ChildKnowledgeState | None) -> list[str]:
    if state is None or _state_code(state) == "unlearned":
        return ["还没有学习证据，可以从动手操作开始。"]
    dimensions = state.dimensions_json or {}
    messages = []
    independent = int(dimensions.get("independent_problem_count", 0))
    representations = dimensions.get("representation", {})
    rep_types = representations.get("types", []) if isinstance(representations, dict) else []
    if independent:
        messages.append(f"已保留 {independent} 道首次独立正确的问题证据。")
    if rep_types:
        messages.append(f"已在 {len(rep_types)} 种表示方式下练习：{'、'.join(rep_types)}。")
    if _state_code(state) == "stable":
        messages.append("证据跨多个自然日且近期仍有成功表现。")
    elif _state_code(state) == "proficient":
        messages.append("已经能够独立完成；稳定掌握还需要跨时间和不同情境。")
    else:
        messages.append("当前仍以理解和练习为主，不根据速度评价。")
    return messages


def _common_difficulties(state: ChildKnowledgeState | None) -> list[str]:
    if state is None:
        return ["暂无学习记录，先观察孩子怎样动手和表达。"]
    messages = []
    if state.hinted_correct_count:
        messages.append("部分任务需要提示，可换成积木或生活物品再操作一次。")
    if state.uncertain_count or state.incorrect_count:
        messages.append("有过犹豫或暂未理解，建议减少数量并请孩子说出自己的想法。")
    representation = (state.dimensions_json or {}).get("representation", {})
    types = representation.get("types", []) if isinstance(representation, dict) else []
    if len(types) < 2:
        messages.append("目前接触的表示方式较少，后续会换一种图形或生活情境。")
    return messages or ["当前没有明显困难；继续用不同物品和情境确认理解。"]


async def math_skill_detail(
    session: AsyncSession,
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    *,
    include_archived: bool = False,
) -> MathSkillDetail | None:
    row = (
        await session.execute(
            select(KnowledgePoint, MathSkill, ChildKnowledgeState)
            .join(MathSkill, MathSkill.knowledge_point_id == KnowledgePoint.id)
            .outerjoin(
                ChildKnowledgeState,
                (ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id)
                & (ChildKnowledgeState.child_id == child_id),
            )
            .where(KnowledgePoint.id == knowledge_point_id)
        )
    ).first()
    if row is None or (not include_archived and row[0].status != KnowledgeStatus.ACTIVE):
        return None
    point, skill, state = row
    navigation = (
        await session.execute(
            select(KnowledgePoint.id, MathSkill.title, MathSkill.order_index)
            .join(MathSkill, MathSkill.knowledge_point_id == KnowledgePoint.id)
            .where(KnowledgePoint.status == KnowledgeStatus.ACTIVE)
            .order_by(MathSkill.order_index)
        )
    ).all()
    current_index = next(
        (index for index, item in enumerate(navigation) if item.id == knowledge_point_id), 0
    )
    templates = list(
        (
            await session.scalars(
                select(MathProblemTemplate)
                .where(MathProblemTemplate.knowledge_point_id == knowledge_point_id)
                .order_by(MathProblemTemplate.order_index)
            )
        ).all()
    )
    prerequisite_rows = (
        await session.execute(
            select(KnowledgePoint.id, MathSkill.title)
            .join(MathSkill, MathSkill.knowledge_point_id == KnowledgePoint.id)
            .join(KnowledgeRelation, KnowledgeRelation.source_id == KnowledgePoint.id)
            .where(
                KnowledgeRelation.target_id == knowledge_point_id,
                KnowledgeRelation.relation_type == RelationType.PREREQUISITE,
            )
            .order_by(MathSkill.order_index)
        )
    ).all()
    schedule = await session.scalar(
        select(ChildReviewSchedule).where(
            ChildReviewSchedule.child_id == child_id,
            ChildReviewSchedule.knowledge_point_id == knowledge_point_id,
        )
    )

    def nav(index: int) -> MathNavigationItem | None:
        if index < 0 or index >= len(navigation):
            return None
        item = navigation[index]
        return MathNavigationItem(knowledge_point_id=item.id, title=item.title)

    summary = math_skill_summary(point, skill, state, template_count=len(templates))
    return MathSkillDetail(
        **summary.model_dump(),
        child_instruction=skill.child_instruction,
        parent_tip=skill.parent_tip,
        recommended_age_min=skill.recommended_age_min,
        recommended_age_max=skill.recommended_age_max,
        generator_key=skill.generator_key,
        settings=skill.settings_json,
        catalog_version=skill.catalog_version,
        templates=[
            MathTemplateSummary(
                id=template.id,
                template_key=template.template_key,
                representation_type=template.representation_type,
                difficulty=template.difficulty,
                generator_version=template.generator_version,
                status=template.status,
            )
            for template in templates
        ],
        prerequisites=[
            MathNavigationItem(knowledge_point_id=item.id, title=item.title)
            for item in prerequisite_rows
        ],
        position=current_index + 1,
        total=len(navigation),
        previous=nav(current_index - 1),
        next=nav(current_index + 1),
        policy_key=MATH_POLICY_KEY,
        dimensions=state.dimensions_json if state else {},
        mastery_explanation=_mastery_explanation(state),
        common_difficulties=_common_difficulties(state),
        last_learning_at=state.last_learning_at if state else None,
        last_assessed_at=state.last_assessed_at if state else None,
        next_review_at=schedule.next_review_at if schedule else None,
    )


async def math_overview(session: AsyncSession, child_id: uuid.UUID) -> MathOverviewResponse:
    rows = (
        await session.execute(
            select(MathSkill.domain, ChildKnowledgeState)
            .join(KnowledgePoint, KnowledgePoint.id == MathSkill.knowledge_point_id)
            .outerjoin(
                ChildKnowledgeState,
                (ChildKnowledgeState.knowledge_point_id == MathSkill.knowledge_point_id)
                & (ChildKnowledgeState.child_id == child_id),
            )
            .where(KnowledgePoint.status == KnowledgeStatus.ACTIVE)
            .order_by(MathSkill.order_index)
        )
    ).all()
    grouped: dict[str, list[str]] = defaultdict(list)
    for domain, state in rows:
        grouped[domain].append(_state_code(state))
    groups = []
    for domain in MATH_DOMAIN_LABELS:
        states = grouped.get(domain, [])
        if not states:
            continue
        learned = sum(state != "unlearned" for state in states)
        proficient = sum(state in {"proficient", "stable"} for state in states)
        stable = sum(state == "stable" for state in states)
        group_state = "unlearned"
        if learned:
            group_state = "introduced"
        if learned >= max(1, len(states) // 3):
            group_state = "practicing"
        if proficient >= max(1, (len(states) + 1) // 2):
            group_state = "proficient"
        if stable == len(states):
            group_state = "stable"
        groups.append(
            MathOverviewGroup(
                domain=domain,
                label=MATH_DOMAIN_LABELS[domain],
                total=len(states),
                learned=learned,
                proficient=proficient,
                stable=stable,
                state_code=group_state,
            )
        )
    all_states = [state for states in grouped.values() for state in states]
    return MathOverviewResponse(
        child_id=child_id,
        catalog_version=MATH_CATALOG_VERSION,
        total=len(all_states),
        learned=sum(state != "unlearned" for state in all_states),
        stable=sum(state == "stable" for state in all_states),
        groups=groups,
    )


async def start_math_session(
    session: AsyncSession,
    child_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    payload: MathSessionStart,
    *,
    now: datetime | None = None,
) -> MathSessionResponse:
    now = now or datetime.now(UTC)
    skill = await session.get(MathSkill, payload.knowledge_point_id)
    point = await session.get(KnowledgePoint, payload.knowledge_point_id)
    if skill is None or point is None or point.status != KnowledgeStatus.ACTIVE:
        raise LookupError("Math skill not found")
    templates = list(
        (
            await session.scalars(
                select(MathProblemTemplate)
                .where(
                    MathProblemTemplate.knowledge_point_id == payload.knowledge_point_id,
                    MathProblemTemplate.status == KnowledgeStatus.ACTIVE,
                )
                .order_by(MathProblemTemplate.order_index)
            )
        ).all()
    )
    if not templates:
        raise LookupError("Math skill has no active problem template")
    base_seed = payload.seed if payload.seed is not None else secrets.randbelow(2_147_000_000)
    previous: MathExerciseAttempt | None = None
    if payload.seed is None:
        previous = await session.scalar(
            select(MathExerciseAttempt)
            .where(
                MathExerciseAttempt.child_id == child_id,
                MathExerciseAttempt.knowledge_point_id == payload.knowledge_point_id,
            )
            .order_by(MathExerciseAttempt.started_at.desc(), MathExerciseAttempt.id.desc())
            .limit(1)
        )
        if previous is not None:
            while base_seed == previous.seed or (
                len(templates) > 1
                and templates[base_seed % len(templates)].id == previous.template_id
            ):
                base_seed = (base_seed + 1) % 2_147_000_000
    if payload.mode == MathAttemptMode.PRACTICE:
        canonical_session: LearningSession | AssessmentSession = LearningSession(
            child_id=child_id,
            actor_user_id=actor_user_id,
            status=SessionStatus.IN_PROGRESS,
            source="math_practice",
            started_at=now,
        )
    else:
        canonical_session = AssessmentSession(
            child_id=child_id,
            evaluator_user_id=actor_user_id,
            status=SessionStatus.IN_PROGRESS,
            source="math_skill_check",
            assessment_kind=AssessmentKind.MATH_CHECK,
            started_at=now,
        )
    session.add(canonical_session)
    await session.flush()
    for index in range(payload.problem_count):
        template = templates[(base_seed + index) % len(templates)]
        problem_seed = (base_seed + index * 7919) % 2_147_483_000
        generated = math_problem_generators.generate(template, problem_seed)
        variation_attempts = 0
        while (
            index == 0
            and previous is not None
            and generated.render_payload == previous.problem_snapshot
            and variation_attempts < 32
        ):
            base_seed = (base_seed + 1) % 2_147_000_000
            template = templates[base_seed % len(templates)]
            problem_seed = base_seed
            generated = math_problem_generators.generate(template, problem_seed)
            variation_attempts += 1
        session.add(
            MathExerciseAttempt(
                child_id=child_id,
                knowledge_point_id=payload.knowledge_point_id,
                session_id=canonical_session.id,
                mode=payload.mode,
                template_id=template.id,
                template_key=generated.template_key,
                generator_version=generated.generator_version,
                seed=generated.seed,
                problem_snapshot=generated.render_payload,
                expected_answer=generated.expected_answer,
                evidence_dimension=payload.dimension,
                started_at=now,
                actor_user_id=actor_user_id,
                evaluator_user_id=(
                    actor_user_id if payload.mode == MathAttemptMode.ASSESSMENT else None
                ),
            )
        )
    await session.commit()
    response = await math_session_response(session, child_id, canonical_session.id)
    assert response is not None
    return response


async def math_session_response(
    session: AsyncSession, child_id: uuid.UUID, session_id: uuid.UUID
) -> MathSessionResponse | None:
    attempts = list(
        (
            await session.scalars(
                select(MathExerciseAttempt)
                .where(
                    MathExerciseAttempt.child_id == child_id,
                    MathExerciseAttempt.session_id == session_id,
                )
                .order_by(MathExerciseAttempt.created_at, MathExerciseAttempt.id)
            )
        ).all()
    )
    if not attempts:
        return None
    skill = await session.get(MathSkill, attempts[0].knowledge_point_id)
    assert skill is not None
    completed_count = sum(attempt.attempt_count > 0 for attempt in attempts)
    return MathSessionResponse(
        session_id=session_id,
        child_id=child_id,
        knowledge_point_id=attempts[0].knowledge_point_id,
        skill_title=skill.title,
        mode=attempts[0].mode,
        dimension=attempts[0].evidence_dimension,
        problems=[
            MathProblemResponse(
                attempt_id=attempt.id,
                template_key=attempt.template_key,
                generator_version=attempt.generator_version,
                seed=attempt.seed,
                representation_type=str(
                    attempt.problem_snapshot.get("representation_type", "objects")
                ),
                render_payload=attempt.problem_snapshot,
                answered=attempt.attempt_count > 0,
            )
            for attempt in attempts
        ],
        completed_count=completed_count,
        total_count=len(attempts),
        completed=completed_count == len(attempts),
    )


async def _update_math_daily_progress(
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
        select(MathDailyPlan).where(
            MathDailyPlan.child_id == child_id, MathDailyPlan.plan_date == plan_date
        )
    )
    if plan is None:
        return
    item = await session.scalar(
        select(MathDailyPlanItem).where(
            MathDailyPlanItem.math_daily_plan_id == plan.id,
            MathDailyPlanItem.knowledge_point_id == knowledge_point_id,
        )
    )
    if item is not None and item.status != PlanItemStatus.COMPLETED:
        item.status = PlanItemStatus.COMPLETED
        item.completed_at = now
    items = list(
        (
            await session.scalars(
                select(MathDailyPlanItem).where(MathDailyPlanItem.math_daily_plan_id == plan.id)
            )
        ).all()
    )
    plan.completed_count = sum(value.status == PlanItemStatus.COMPLETED for value in items)
    if items and plan.completed_count == len(items):
        plan.status = DailyPlanStatus.COMPLETED
    elif plan.completed_count:
        plan.status = DailyPlanStatus.IN_PROGRESS


async def answer_math_attempt(
    session: AsyncSession,
    child_id: uuid.UUID,
    session_id: uuid.UUID,
    attempt_id: uuid.UUID,
    _actor_user_id: uuid.UUID,
    payload: MathAttemptAnswer,
    *,
    now: datetime | None = None,
) -> MathAttemptAnswerResponse:
    now = now or datetime.now(UTC)
    attempt = await session.scalar(
        select(MathExerciseAttempt).where(
            MathExerciseAttempt.id == attempt_id,
            MathExerciseAttempt.session_id == session_id,
            MathExerciseAttempt.child_id == child_id,
        )
    )
    if attempt is None:
        raise LookupError("Math attempt not found")
    if attempt.mode == MathAttemptMode.ASSESSMENT and attempt.attempt_count > 0:
        raise RuntimeError("Assessment first answer is already preserved")
    first_submission = attempt.attempt_count == 0
    if first_submission:
        attempt.first_answer = payload.submitted_answer
    attempt.submitted_answer = payload.submitted_answer
    attempt.attempt_count += 1
    attempt.hint_used = attempt.hint_used or payload.hint_used
    attempt.answered_at = now
    attempt.response_time_ms = payload.response_time_ms
    is_correct = payload.submitted_answer == attempt.expected_answer
    first_correct = attempt.first_answer == attempt.expected_answer
    if is_correct and attempt.attempt_count == 1 and not attempt.hint_used:
        attempt.outcome = AssessmentOutcome.CORRECT
        feedback = "对啦！"
    elif is_correct and attempt.attempt_count > 1:
        attempt.outcome = AssessmentOutcome.UNCERTAIN
        feedback = "找到了！第一次的想法也已经保留下来。"
    elif is_correct and attempt.hint_used:
        attempt.outcome = AssessmentOutcome.HINTED_CORRECT
        feedback = "在提示下找到了，我们再换一种看看。"
    else:
        attempt.outcome = AssessmentOutcome.INCORRECT
        feedback = "再看看，有几个呢？"
    await session.flush()

    attempts = list(
        (
            await session.scalars(
                select(MathExerciseAttempt).where(
                    MathExerciseAttempt.child_id == child_id,
                    MathExerciseAttempt.session_id == session_id,
                )
            )
        ).all()
    )
    completed = all(value.attempt_count > 0 for value in attempts)
    mastery_state: str | None = None
    if completed:
        if attempt.mode == MathAttemptMode.PRACTICE:
            learning_session = await session.get(LearningSession, session_id)
            if learning_session is None:
                raise RuntimeError("Math learning session not found")
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
                        source="math_practice",
                        learned_at=now,
                    )
                )
            learning_session.status = SessionStatus.COMPLETED
            learning_session.completed_at = now
        else:
            assessment_session = await session.get(AssessmentSession, session_id)
            if assessment_session is None:
                raise RuntimeError("Math assessment session not found")
            existing_item = await session.scalar(
                select(AssessmentItem).where(
                    AssessmentItem.session_id == session_id,
                    AssessmentItem.knowledge_point_id == attempt.knowledge_point_id,
                )
            )
            if existing_item is None:
                outcomes = [value.outcome for value in attempts]
                correct_count = sum(value == AssessmentOutcome.CORRECT for value in outcomes)
                hinted_count = sum(value == AssessmentOutcome.HINTED_CORRECT for value in outcomes)
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
                representations = sorted(
                    {
                        str(value.problem_snapshot.get("representation_type", "objects"))
                        for value in attempts
                    }
                )
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
                            "policy_key": MATH_POLICY_KEY,
                            "problem_count": len(attempts),
                            "correct_attempts": correct_count,
                            "first_answer_correct_count": sum(
                                value.first_answer == value.expected_answer for value in attempts
                            ),
                            "representations": representations,
                            "template_keys": sorted({value.template_key for value in attempts}),
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
        await _update_math_daily_progress(session, child_id, attempt.knowledge_point_id, now=now)
        mastery_state = _state_code(state)
    await session.commit()
    return MathAttemptAnswerResponse(
        attempt_id=attempt.id,
        outcome=attempt.outcome,
        first_answer_correct=first_correct,
        attempt_count=attempt.attempt_count,
        hint_used=attempt.hint_used,
        feedback=feedback,
        correct_answer=attempt.expected_answer,
        session_completed=completed,
        mastery_state=mastery_state,
    )


async def record_math_offline_observation(
    session: AsyncSession,
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    payload: MathOfflineObservationInput,
    *,
    now: datetime | None = None,
) -> MathOfflineObservationResponse:
    """Persist one real-world parent observation without bypassing math-v1."""

    now = now or datetime.now(UTC)
    point = await session.get(KnowledgePoint, knowledge_point_id)
    skill = await session.get(MathSkill, knowledge_point_id)
    if point is None or skill is None or point.status != KnowledgeStatus.ACTIVE:
        raise LookupError("Math skill not found")
    assessment_session = AssessmentSession(
        child_id=child_id,
        evaluator_user_id=actor_user_id,
        status=SessionStatus.COMPLETED,
        source="math_offline_observation",
        assessment_kind=AssessmentKind.MATH_CHECK,
        started_at=now,
        completed_at=now,
    )
    session.add(assessment_session)
    await session.flush()
    independent = payload.outcome == AssessmentOutcome.CORRECT
    item = AssessmentItem(
        session_id=assessment_session.id,
        child_id=child_id,
        knowledge_point_id=knowledge_point_id,
        evaluator_user_id=actor_user_id,
        outcome=payload.outcome,
        hint_used=payload.outcome == AssessmentOutcome.HINTED_CORRECT,
        skill_dimension="transfer" if independent else "understanding",
        evidence_metadata={
            "policy_key": MATH_POLICY_KEY,
            "offline_observation": True,
            "problem_count": 1,
            "correct_attempts": int(independent),
            "first_answer_correct_count": int(independent),
            "representations": ["offline_objects"],
        },
        assessed_at=now,
    )
    session.add(item)
    await session.flush()
    state = await recompute_child_knowledge_state(
        session, child_id, knowledge_point_id, ensure_state=True
    )
    await recompute_review_schedule(session, child_id, knowledge_point_id)
    await _update_math_daily_progress(session, child_id, knowledge_point_id, now=now)
    await session.commit()
    return MathOfflineObservationResponse(
        assessment_item_id=item.id,
        outcome=payload.outcome,
        mastery_state=_state_code(state),
    )


async def get_or_create_math_today(
    session: AsyncSession, child_id: uuid.UUID, *, now: datetime | None = None
) -> MathTodayResponse | None:
    now = now or datetime.now(UTC)
    settings = await session.scalar(
        select(ChildLearningSettings).where(ChildLearningSettings.child_id == child_id)
    )
    timezone_name = settings.timezone if settings else "Asia/Shanghai"
    plan_date = now.astimezone(ZoneInfo(timezone_name)).date()
    plan = await session.scalar(
        select(MathDailyPlan).where(
            MathDailyPlan.child_id == child_id, MathDailyPlan.plan_date == plan_date
        )
    )
    if plan is None:
        catalog_exists = await session.scalar(select(MathSkill.knowledge_point_id).limit(1))
        if catalog_exists is None:
            return None
        new_rows = (
            await session.execute(
                select(KnowledgePoint, MathSkill)
                .join(MathSkill, MathSkill.knowledge_point_id == KnowledgePoint.id)
                .outerjoin(
                    ChildKnowledgeState,
                    (ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id)
                    & (ChildKnowledgeState.child_id == child_id),
                )
                .where(
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChildKnowledgeState.id.is_(None),
                )
                .order_by(MathSkill.order_index)
                .limit(MATH_NEW_LIMIT)
            )
        ).all()
        review_rows = (
            await session.execute(
                select(KnowledgePoint, MathSkill)
                .join(MathSkill, MathSkill.knowledge_point_id == KnowledgePoint.id)
                .join(
                    ChildReviewSchedule,
                    (ChildReviewSchedule.knowledge_point_id == KnowledgePoint.id)
                    & (ChildReviewSchedule.child_id == child_id),
                )
                .where(
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChildReviewSchedule.algorithm_version == MATH_REVIEW_ALGORITHM_VERSION,
                    ChildReviewSchedule.next_review_at <= now,
                )
                .order_by(ChildReviewSchedule.next_review_at, MathSkill.order_index)
                .limit(MATH_REVIEW_LIMIT)
            )
        ).all()
        plan = MathDailyPlan(
            child_id=child_id,
            plan_date=plan_date,
            timezone=timezone_name,
            new_count=len(new_rows),
            review_count=len(review_rows),
            completed_count=0,
            status=DailyPlanStatus.PENDING,
            algorithm_version="math-plan-v1",
        )
        session.add(plan)
        await session.flush()
        new_ids = {point.id for point, _skill in new_rows}
        selected = [(row, "new", 3) for row in new_rows] + [
            (row, "review", 2) for row in review_rows if row[0].id not in new_ids
        ]
        for position, ((point, _skill), kind, problem_count) in enumerate(selected):
            session.add(
                MathDailyPlanItem(
                    math_daily_plan_id=plan.id,
                    knowledge_point_id=point.id,
                    item_kind=kind,
                    status=PlanItemStatus.PENDING,
                    position=position,
                    problem_count=problem_count,
                )
            )
        plan.review_count = sum(kind == "review" for _row, kind, _count in selected)
        await session.flush()
    return await _math_today_response(session, plan)


async def _math_today_response(session: AsyncSession, plan: MathDailyPlan) -> MathTodayResponse:
    rows = (
        await session.execute(
            select(MathDailyPlanItem, KnowledgePoint, MathSkill, ChildKnowledgeState)
            .join(KnowledgePoint, KnowledgePoint.id == MathDailyPlanItem.knowledge_point_id)
            .join(MathSkill, MathSkill.knowledge_point_id == KnowledgePoint.id)
            .outerjoin(
                ChildKnowledgeState,
                (ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id)
                & (ChildKnowledgeState.child_id == plan.child_id),
            )
            .where(MathDailyPlanItem.math_daily_plan_id == plan.id)
            .order_by(MathDailyPlanItem.position)
        )
    ).all()
    counts = await _template_counts(session)
    items = [
        MathTodayItem(
            **math_skill_summary(
                point, skill, state, template_count=counts.get(point.id, 0)
            ).model_dump(),
            item_kind=plan_item.item_kind,
            problem_count=plan_item.problem_count,
            completed=plan_item.status == PlanItemStatus.COMPLETED,
        )
        for plan_item, point, skill, state in rows
    ]
    return MathTodayResponse(
        plan_id=plan.id,
        child_id=plan.child_id,
        plan_date=plan.plan_date,
        items=items,
        completed_count=plan.completed_count,
        target_count=len(items),
        status=plan.status,
        estimated_minutes=5 if len(items) <= 2 else 8,
    )


async def math_history(
    session: AsyncSession, child_id: uuid.UUID, *, limit: int = 30
) -> MathHistoryResponse:
    rows = (
        await session.execute(
            select(MathExerciseAttempt, MathSkill, User)
            .join(MathSkill, MathSkill.knowledge_point_id == MathExerciseAttempt.knowledge_point_id)
            .join(User, User.id == MathExerciseAttempt.actor_user_id)
            .where(MathExerciseAttempt.child_id == child_id)
            .order_by(MathExerciseAttempt.started_at.desc())
            .limit(limit * 10)
        )
    ).all()
    grouped: dict[
        tuple[uuid.UUID, str, str, datetime], list[tuple[MathExerciseAttempt, MathSkill]]
    ] = defaultdict(list)
    for attempt, skill, user in rows:
        key = (attempt.session_id, attempt.mode, user.display_name, attempt.started_at)
        grouped[key].append((attempt, skill))
    output = []
    for (session_id, mode, actor, occurred_at), values in grouped.items():
        by_skill: dict[uuid.UUID, list[tuple[MathExerciseAttempt, MathSkill]]] = defaultdict(list)
        for value in values:
            by_skill[value[0].knowledge_point_id].append(value)
        skills = []
        for point_id, attempts in by_skill.items():
            skill = attempts[0][1]
            outcomes = [item[0].outcome for item in attempts]
            skills.append(
                MathHistorySkill(
                    knowledge_point_id=point_id,
                    title=skill.title,
                    domain=skill.domain,
                    problem_count=len(attempts),
                    correct=outcomes.count(AssessmentOutcome.CORRECT),
                    hinted_correct=outcomes.count(AssessmentOutcome.HINTED_CORRECT),
                    uncertain=outcomes.count(AssessmentOutcome.UNCERTAIN),
                    incorrect=outcomes.count(AssessmentOutcome.INCORRECT),
                    representations=sorted(
                        {
                            str(item[0].problem_snapshot.get("representation_type", "objects"))
                            for item in attempts
                        }
                    ),
                )
            )
        output.append(
            MathHistorySession(
                session_id=session_id,
                mode=mode,
                actor_display_name=actor,
                occurred_at=occurred_at,
                skills=skills,
            )
        )
    output.sort(key=lambda item: item.occurred_at, reverse=True)
    offline_rows = (
        await session.execute(
            select(AssessmentItem, MathSkill, User, AssessmentSession)
            .join(MathSkill, MathSkill.knowledge_point_id == AssessmentItem.knowledge_point_id)
            .join(User, User.id == AssessmentItem.evaluator_user_id)
            .join(AssessmentSession, AssessmentSession.id == AssessmentItem.session_id)
            .where(
                AssessmentItem.child_id == child_id,
                AssessmentSession.source == "math_offline_observation",
            )
            .order_by(AssessmentItem.assessed_at.desc())
            .limit(limit)
        )
    ).all()
    for item, skill, user, assessment_session in offline_rows:
        output.append(
            MathHistorySession(
                session_id=assessment_session.id,
                mode="offline",
                actor_display_name=user.display_name,
                occurred_at=item.assessed_at,
                skills=[
                    MathHistorySkill(
                        knowledge_point_id=item.knowledge_point_id,
                        title=skill.title,
                        domain=skill.domain,
                        problem_count=1,
                        correct=int(item.outcome == AssessmentOutcome.CORRECT),
                        hinted_correct=int(item.outcome == AssessmentOutcome.HINTED_CORRECT),
                        uncertain=int(item.outcome == AssessmentOutcome.UNCERTAIN),
                        incorrect=int(item.outcome == AssessmentOutcome.INCORRECT),
                        representations=["offline_objects"],
                    )
                ],
            )
        )
    output.sort(key=lambda item: item.occurred_at, reverse=True)
    return MathHistoryResponse(child_id=child_id, items=output[:limit])
