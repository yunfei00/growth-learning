"""Derived child experience, growth tree, achievements, and encouragement rules."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AchievementDefinition,
    ActivityKnowledgePoint,
    AssessmentSession,
    Child,
    ChildAchievement,
    ChildCourseEnrollment,
    ChildKnowledgeState,
    Course,
    CourseActivityProgress,
    CourseUnit,
    ExperimentEvidence,
    ExperimentSession,
    FamilyRewardGoal,
    FamilyRewardSettings,
    LearningActivity,
    LearningRecord,
    ReadingSession,
    ScienceExperiment,
    StarLedger,
    TeacherAssignmentProgress,
    User,
)
from app.schemas.experience import (
    AchievementRebuildResponse,
    AchievementResponse,
    AchievementSummaryResponse,
    ChildTodayResponse,
    GrowthTreeCourseResponse,
    GrowthTreeDomainResponse,
    GrowthTreeResponse,
    GrowthTreeUnitResponse,
    RewardGoalResponse,
    RewardSettingsResponse,
    StarLedgerResponse,
    TodayTaskResponse,
)
from app.services.review_planning import get_or_create_daily_plan
from app.services.teacher_collaboration import list_child_teacher_tasks

ACHIEVEMENT_RULE_VERSION = "achievement-v1"
REWARD_RULE_VERSION = "stars-v1"
GROWTH_TREE_VERSION = "growth-tree-v1"

ACHIEVEMENT_RULES: tuple[dict[str, object], ...] = (
    {
        "key": "first_learning",
        "title": "第一次学习",
        "description": "完成第一次真实识字学习",
        "icon": "🌱",
        "rule_type": "learning_records",
        "threshold": 1,
    },
    {
        "key": "learning_10_characters",
        "title": "种下10颗种子",
        "description": "真实接触10个不同汉字",
        "icon": "🌿",
        "rule_type": "distinct_learning_points",
        "threshold": 10,
    },
    {
        "key": "stable_10_characters",
        "title": "10片熟悉的新叶",
        "description": "稳定掌握10个汉字",
        "icon": "🍃",
        "rule_type": "stable_points",
        "threshold": 10,
    },
    {
        "key": "stable_50_characters",
        "title": "茂盛的小树冠",
        "description": "稳定掌握50个汉字",
        "icon": "🌳",
        "rule_type": "stable_points",
        "threshold": 50,
    },
    {
        "key": "first_review",
        "title": "第一次复习",
        "description": "完成第一次今日复习",
        "icon": "🔁",
        "rule_type": "completed_reviews",
        "threshold": 1,
    },
    {
        "key": "learning_7_days",
        "title": "一周成长足迹",
        "description": "在7个不同日期留下真实学习记录",
        "icon": "🗓️",
        "rule_type": "learning_days",
        "threshold": 7,
    },
    {
        "key": "first_independent_story",
        "title": "第一次自己读故事",
        "description": "独立读完第一个故事",
        "icon": "📖",
        "rule_type": "independent_readings",
        "threshold": 1,
    },
    {
        "key": "stories_10",
        "title": "故事小书迷",
        "description": "读完10个故事",
        "icon": "📚",
        "rule_type": "completed_readings",
        "threshold": 10,
    },
    {
        "key": "first_science",
        "title": "第一次科学探索",
        "description": "完成第一次科学实验",
        "icon": "🔬",
        "rule_type": "completed_experiments",
        "threshold": 1,
    },
    {
        "key": "science_5",
        "title": "科学探索家",
        "description": "完成5次科学实验",
        "icon": "🧪",
        "rule_type": "completed_experiments",
        "threshold": 5,
    },
    {
        "key": "first_science_question",
        "title": "好奇的小问号",
        "description": "第一次主动提出科学问题",
        "icon": "❓",
        "rule_type": "science_questions",
        "threshold": 1,
    },
    {
        "key": "first_teacher_task",
        "title": "老师任务初体验",
        "description": "完成老师布置的第一个任务",
        "icon": "🧑‍🏫",
        "rule_type": "completed_teacher_tasks",
        "threshold": 1,
    },
)


@dataclass(frozen=True)
class RuleEvidence:
    count: int
    source_type: str
    source_id: uuid.UUID | None
    occurred_at: datetime | None


async def ensure_achievement_definitions(session: AsyncSession) -> list[AchievementDefinition]:
    existing = {
        item.key: item
        for item in await session.scalars(
            select(AchievementDefinition).order_by(AchievementDefinition.key)
        )
    }
    for rule in ACHIEVEMENT_RULES:
        key = str(rule["key"])
        definition = existing.get(key)
        if definition is None:
            definition = AchievementDefinition(
                key=key,
                title=str(rule["title"]),
                description=str(rule["description"]),
                icon=str(rule["icon"]),
                rule_type=str(rule["rule_type"]),
                threshold=int(rule["threshold"]),
                rule_version=ACHIEVEMENT_RULE_VERSION,
            )
            session.add(definition)
            existing[key] = definition
        else:
            definition.title = str(rule["title"])
            definition.description = str(rule["description"])
            definition.icon = str(rule["icon"])
            definition.rule_type = str(rule["rule_type"])
            definition.threshold = int(rule["threshold"])
            definition.rule_version = ACHIEVEMENT_RULE_VERSION
            definition.is_enabled = True
    await session.flush()
    return sorted(existing.values(), key=lambda item: item.key)


async def _first_and_count(
    session: AsyncSession,
    model: type,
    *conditions: object,
    id_column: object,
    time_column: object,
    distinct_column: object | None = None,
) -> RuleEvidence:
    count_expression = (
        func.count(func.distinct(distinct_column)) if distinct_column is not None else func.count()
    )
    count = int(
        await session.scalar(select(count_expression).select_from(model).where(*conditions)) or 0
    )
    first = (
        await session.execute(
            select(id_column, time_column)
            .where(*conditions)
            .order_by(time_column, id_column)
            .limit(1)
        )
    ).one_or_none()
    return RuleEvidence(
        count=count,
        source_type=model.__tablename__,
        source_id=first[0] if first else None,
        occurred_at=first[1] if first else None,
    )


async def _rule_evidence(
    session: AsyncSession, child_id: uuid.UUID, rule_type: str
) -> RuleEvidence:
    if rule_type == "learning_records":
        return await _first_and_count(
            session,
            LearningRecord,
            LearningRecord.child_id == child_id,
            id_column=LearningRecord.id,
            time_column=LearningRecord.learned_at,
        )
    if rule_type == "distinct_learning_points":
        return await _first_and_count(
            session,
            LearningRecord,
            LearningRecord.child_id == child_id,
            id_column=LearningRecord.id,
            time_column=LearningRecord.learned_at,
            distinct_column=LearningRecord.knowledge_point_id,
        )
    if rule_type == "stable_points":
        return await _first_and_count(
            session,
            ChildKnowledgeState,
            ChildKnowledgeState.child_id == child_id,
            ChildKnowledgeState.mastery_level == "stable",
            id_column=ChildKnowledgeState.id,
            time_column=ChildKnowledgeState.updated_at,
        )
    if rule_type == "completed_reviews":
        return await _first_and_count(
            session,
            AssessmentSession,
            AssessmentSession.child_id == child_id,
            AssessmentSession.status == "completed",
            AssessmentSession.source == "daily_review",
            id_column=AssessmentSession.id,
            time_column=AssessmentSession.completed_at,
        )
    if rule_type == "learning_days":
        evidence = await _first_and_count(
            session,
            LearningRecord,
            LearningRecord.child_id == child_id,
            id_column=LearningRecord.id,
            time_column=LearningRecord.learned_at,
            distinct_column=func.date(LearningRecord.learned_at),
        )
        return RuleEvidence(
            evidence.count, "learning_days", evidence.source_id, evidence.occurred_at
        )
    if rule_type in {"independent_readings", "completed_readings"}:
        conditions: list[object] = [
            ReadingSession.child_id == child_id,
            ReadingSession.status == "completed",
        ]
        if rule_type == "independent_readings":
            conditions.append(ReadingSession.reading_mode == "independent")
        return await _first_and_count(
            session,
            ReadingSession,
            *conditions,
            id_column=ReadingSession.id,
            time_column=ReadingSession.completed_at,
        )
    if rule_type == "completed_experiments":
        return await _first_and_count(
            session,
            ExperimentSession,
            ExperimentSession.child_id == child_id,
            ExperimentSession.status == "completed",
            id_column=ExperimentSession.id,
            time_column=ExperimentSession.completed_at,
        )
    if rule_type == "science_questions":
        return await _first_and_count(
            session,
            ExperimentEvidence,
            ExperimentEvidence.child_id == child_id,
            ExperimentEvidence.evidence_type == "question_asked",
            id_column=ExperimentEvidence.id,
            time_column=ExperimentEvidence.captured_at,
        )
    if rule_type == "completed_teacher_tasks":
        return await _first_and_count(
            session,
            TeacherAssignmentProgress,
            TeacherAssignmentProgress.child_id == child_id,
            TeacherAssignmentProgress.status == "completed",
            id_column=TeacherAssignmentProgress.id,
            time_column=TeacherAssignmentProgress.completed_at,
        )
    raise ValueError(f"Unsupported achievement rule: {rule_type}")


async def ensure_reward_settings(
    session: AsyncSession, family_id: uuid.UUID
) -> FamilyRewardSettings:
    settings = await session.scalar(
        select(FamilyRewardSettings).where(FamilyRewardSettings.family_id == family_id)
    )
    if settings is None:
        settings = FamilyRewardSettings(family_id=family_id)
        session.add(settings)
        await session.flush()
    return settings


async def _grant_star(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    amount: int,
    reason_type: str,
    source_type: str,
    source_id: uuid.UUID,
    occurred_at: datetime | None,
) -> bool:
    if amount <= 0:
        raise ValueError("Star rewards must be positive")
    existing = await session.scalar(
        select(StarLedger.id).where(
            StarLedger.child_id == child_id,
            StarLedger.reason_type == reason_type,
            StarLedger.source_type == source_type,
            StarLedger.source_id == source_id,
            StarLedger.rule_version == REWARD_RULE_VERSION,
        )
    )
    if existing is not None:
        return False
    session.add(
        StarLedger(
            child_id=child_id,
            amount=amount,
            reason_type=reason_type,
            source_type=source_type,
            source_id=source_id,
            rule_version=REWARD_RULE_VERSION,
            occurred_at=occurred_at or datetime.now(UTC),
        )
    )
    await session.flush()
    return True


async def sync_star_ledger(
    session: AsyncSession, child: Child, achievements: list[ChildAchievement]
) -> int:
    settings = await ensure_reward_settings(session, child.family_id)
    if not settings.stars_enabled:
        return 0
    created = 0
    for achievement in achievements:
        created += int(
            await _grant_star(
                session,
                child_id=child.id,
                amount=2,
                reason_type="achievement",
                source_type="child_achievement",
                source_id=achievement.id,
                occurred_at=achievement.unlocked_at,
            )
        )
    reward_sources: tuple[tuple[type, tuple[object, ...], str, int, object], ...] = (
        (
            AssessmentSession,
            (
                AssessmentSession.child_id == child.id,
                AssessmentSession.status == "completed",
                AssessmentSession.source == "daily_review",
            ),
            "completed_review",
            2,
            AssessmentSession.completed_at,
        ),
        (
            ReadingSession,
            (ReadingSession.child_id == child.id, ReadingSession.status == "completed"),
            "completed_reading",
            2,
            ReadingSession.completed_at,
        ),
        (
            ExperimentSession,
            (ExperimentSession.child_id == child.id, ExperimentSession.status == "completed"),
            "completed_science",
            3,
            ExperimentSession.completed_at,
        ),
        (
            TeacherAssignmentProgress,
            (
                TeacherAssignmentProgress.child_id == child.id,
                TeacherAssignmentProgress.status == "completed",
            ),
            "completed_teacher_task",
            2,
            TeacherAssignmentProgress.completed_at,
        ),
    )
    for model, conditions, reason, amount, time_column in reward_sources:
        rows = (await session.execute(select(model.id, time_column).where(*conditions))).all()
        for source_id, occurred_at in rows:
            created += int(
                await _grant_star(
                    session,
                    child_id=child.id,
                    amount=amount,
                    reason_type=reason,
                    source_type=model.__tablename__,
                    source_id=source_id,
                    occurred_at=occurred_at,
                )
            )
    return created


async def rebuild_child_achievements(
    session: AsyncSession, child: Child
) -> AchievementRebuildResponse:
    definitions = await ensure_achievement_definitions(session)
    existing = {
        item.achievement_definition_id: item
        for item in await session.scalars(
            select(ChildAchievement).where(ChildAchievement.child_id == child.id)
        )
    }
    created = 0
    for definition in definitions:
        if not definition.is_enabled or definition.id in existing:
            continue
        evidence = await _rule_evidence(session, child.id, definition.rule_type)
        if evidence.count < definition.threshold:
            continue
        unlock = ChildAchievement(
            child_id=child.id,
            achievement_definition_id=definition.id,
            rule_version=definition.rule_version,
            evidence_source_type=evidence.source_type,
            evidence_source_id=evidence.source_id,
            evidence_snapshot={
                "rule_type": definition.rule_type,
                "threshold": definition.threshold,
                "observed_count": evidence.count,
                "projection_version": definition.rule_version,
            },
            unlocked_at=evidence.occurred_at or datetime.now(UTC),
        )
        session.add(unlock)
        await session.flush()
        existing[definition.id] = unlock
        created += 1
    achievements = list(existing.values())
    rewards_created = await sync_star_ledger(session, child, achievements)
    await session.commit()
    balance = int(
        await session.scalar(
            select(func.coalesce(func.sum(StarLedger.amount), 0)).where(
                StarLedger.child_id == child.id
            )
        )
        or 0
    )
    return AchievementRebuildResponse(
        child_id=child.id,
        definitions=len(definitions),
        created=created,
        existing=len(achievements) - created,
        rewards_created=rewards_created,
        star_balance=balance,
    )


def _achievement_response(
    achievement: ChildAchievement, definition: AchievementDefinition
) -> AchievementResponse:
    return AchievementResponse(
        id=achievement.id,
        key=definition.key,
        title=definition.title,
        description=definition.description,
        icon=definition.icon,
        rule_version=achievement.rule_version,
        evidence_source_type=achievement.evidence_source_type,
        evidence_source_id=achievement.evidence_source_id,
        evidence_snapshot=achievement.evidence_snapshot,
        unlocked_at=achievement.unlocked_at,
    )


async def achievement_summary(session: AsyncSession, child: Child) -> AchievementSummaryResponse:
    await rebuild_child_achievements(session, child)
    rows = (
        await session.execute(
            select(ChildAchievement, AchievementDefinition)
            .join(
                AchievementDefinition,
                AchievementDefinition.id == ChildAchievement.achievement_definition_id,
            )
            .where(ChildAchievement.child_id == child.id)
            .order_by(ChildAchievement.unlocked_at.desc(), ChildAchievement.id)
        )
    ).all()
    ledger = list(
        await session.scalars(
            select(StarLedger)
            .where(StarLedger.child_id == child.id)
            .order_by(StarLedger.occurred_at.desc(), StarLedger.id)
            .limit(20)
        )
    )
    balance = int(
        await session.scalar(
            select(func.coalesce(func.sum(StarLedger.amount), 0)).where(
                StarLedger.child_id == child.id
            )
        )
        or 0
    )
    settings = await ensure_reward_settings(session, child.family_id)
    goal = await session.scalar(
        select(FamilyRewardGoal)
        .where(
            FamilyRewardGoal.family_id == child.family_id,
            FamilyRewardGoal.is_active.is_(True),
            FamilyRewardGoal.required_stars > balance,
        )
        .order_by(FamilyRewardGoal.required_stars, FamilyRewardGoal.created_at)
    )
    await session.commit()
    return AchievementSummaryResponse(
        child_id=child.id,
        stars_enabled=settings.stars_enabled,
        star_balance=balance,
        achievements=[_achievement_response(item, definition) for item, definition in rows],
        recent_ledger=[StarLedgerResponse.model_validate(item) for item in ledger],
        next_reward_goal=(RewardGoalResponse.model_validate(goal) if goal else None),
    )


async def child_today(session: AsyncSession, child: Child, user: User) -> ChildTodayResponse:
    rebuilt = await rebuild_child_achievements(session, child)
    plan = await get_or_create_daily_plan(session, child.id)
    tasks: list[TodayTaskResponse] = []
    if plan.recommended_new_count:
        status = (
            "completed"
            if plan.new_completed_count >= plan.recommended_new_count
            else ("in_progress" if plan.new_completed_count else "pending")
        )
        tasks.append(
            TodayTaskResponse(
                kind="new",
                title=f"学{plan.recommended_new_count}个新字",
                description="按今天的课程顺序认识新朋友",
                status=status,
                count=plan.recommended_new_count,
                cta_label="继续学习" if status == "in_progress" else "开始学习",
                href="/learn/characters",
                source_type="daily_learning_plan",
                source_id=plan.id,
            )
        )
    in_progress_assessment = await session.scalar(
        select(AssessmentSession)
        .where(
            AssessmentSession.child_id == child.id,
            AssessmentSession.status == "in_progress",
            AssessmentSession.source.in_(["daily_review", "weekly_check", "monthly_assessment"]),
        )
        .order_by(AssessmentSession.started_at.desc())
    )
    if plan.review_count or in_progress_assessment:
        review_count = max(plan.review_count, 1 if in_progress_assessment else 0)
        status = (
            "completed"
            if plan.review_count and plan.review_completed_count >= plan.review_count
            else (
                "in_progress"
                if in_progress_assessment or plan.review_completed_count
                else "pending"
            )
        )
        tasks.append(
            TodayTaskResponse(
                kind="review",
                title=f"复习{review_count}个字",
                description="让已经认识的字长出新叶子",
                status=status,
                count=review_count,
                cta_label="继续复习" if status == "in_progress" else "开始复习",
                href="/learn/characters",
                source_type="assessment_session"
                if in_progress_assessment
                else "daily_learning_plan",
                source_id=in_progress_assessment.id if in_progress_assessment else plan.id,
            )
        )
    reading = plan.reading
    tasks.append(
        TodayTaskResponse(
            kind="reading",
            title=reading.title or "读一个故事",
            description=(
                "故事准备好啦"
                if reading.status in {"pending", "in_progress", "completed"}
                else "请让爸爸妈妈先准备一个故事"
            ),
            status=reading.status,
            count=1,
            cta_label=("继续阅读" if reading.status == "in_progress" else "去看故事"),
            href=(f"/read/{reading.story_version_id}" if reading.story_version_id else "/read"),
            source_type="reading_session" if reading.reading_session_id else "daily_reading_task",
            source_id=reading.reading_session_id,
        )
    )
    teacher_tasks = await list_child_teacher_tasks(session, user, child.id)
    for task in teacher_tasks:
        if task.progress_status == "completed":
            status = "completed"
        elif task.progress_status == "in_progress":
            status = "in_progress"
        else:
            status = "pending"
        urgent = bool(task.due_at and task.due_at <= datetime.now(UTC) + timedelta(days=1))
        tasks.append(
            TodayTaskResponse(
                kind="teacher",
                title=task.title,
                description=f"{task.teacher.display_name}的小挑战",
                status=status,
                count=max(task.total_item_count, 1),
                cta_label="继续挑战" if status == "in_progress" else "开始挑战",
                href=f"/teacher-tasks/{task.assignment_id}/{child.id}",
                source_type="teacher_assignment",
                source_id=task.assignment_id,
                urgent=urgent,
            )
        )
    science_session = await session.scalar(
        select(ExperimentSession)
        .where(ExperimentSession.child_id == child.id, ExperimentSession.status == "in_progress")
        .order_by(ExperimentSession.updated_at.desc())
    )
    science_available = bool(
        await session.scalar(
            select(ScienceExperiment.id).where(ScienceExperiment.status == "enabled").limit(1)
        )
    )
    if science_session:
        title = str(science_session.experiment_snapshot.get("title", "科学实验"))
        tasks.append(
            TodayTaskResponse(
                kind="science",
                title=title,
                description="实验还在等你继续探索",
                status="in_progress",
                count=1,
                cta_label="继续实验",
                href=f"/science/session/{science_session.id}",
                source_type="experiment_session",
                source_id=science_session.id,
            )
        )
    elif science_available:
        tasks.append(
            TodayTaskResponse(
                kind="science",
                title="周末科学实验",
                description="和爸爸妈妈一起选择一个小实验",
                status="optional",
                count=1,
                cta_label="去探索",
                href="/science",
                source_type="science_catalog",
                source_id=None,
            )
        )
    order = {"teacher": 0, "review": 1, "new": 2, "reading": 3, "science": 4}
    tasks.sort(key=lambda item: (not item.urgent, order[item.kind]))
    continue_task = next((item for item in tasks if item.status == "in_progress"), None)
    completed_count = sum(item.status == "completed" for item in tasks)
    return ChildTodayResponse(
        child_id=child.id,
        plan_date=plan.plan_date,
        tasks=tasks,
        continue_task=continue_task,
        completed_count=completed_count,
        total_count=len(tasks),
        star_balance=rebuilt.star_balance,
        newly_unlocked_achievements=rebuilt.created,
    )


async def growth_tree(session: AsyncSession, child: Child) -> GrowthTreeResponse:
    rows = (
        await session.execute(
            select(
                ChildCourseEnrollment,
                Course,
                CourseUnit,
                func.count(func.distinct(LearningActivity.id)).label("activity_count"),
                func.count(
                    func.distinct(
                        case(
                            (
                                CourseActivityProgress.status == "completed",
                                CourseActivityProgress.activity_id,
                            )
                        )
                    )
                ).label("completed_activities"),
                func.count(func.distinct(ActivityKnowledgePoint.knowledge_point_id)).label("total"),
                func.count(
                    func.distinct(
                        case(
                            (
                                ChildKnowledgeState.mastery_level.in_(
                                    ["introduced", "recognizing", "proficient", "stable"]
                                ),
                                ActivityKnowledgePoint.knowledge_point_id,
                            )
                        )
                    )
                ).label("touched"),
                func.count(
                    func.distinct(
                        case(
                            (
                                ChildKnowledgeState.mastery_level.in_(
                                    ["introduced", "recognizing", "proficient"]
                                ),
                                ActivityKnowledgePoint.knowledge_point_id,
                            )
                        )
                    )
                ).label("growing"),
                func.count(
                    func.distinct(
                        case(
                            (
                                ChildKnowledgeState.mastery_level == "stable",
                                ActivityKnowledgePoint.knowledge_point_id,
                            )
                        )
                    )
                ).label("familiar"),
            )
            .join(Course, Course.id == ChildCourseEnrollment.course_id)
            .join(CourseUnit, CourseUnit.course_id == Course.id)
            .join(LearningActivity, LearningActivity.course_unit_id == CourseUnit.id)
            .outerjoin(
                ActivityKnowledgePoint,
                ActivityKnowledgePoint.activity_id == LearningActivity.id,
            )
            .outerjoin(
                ChildKnowledgeState,
                and_(
                    ChildKnowledgeState.child_id == child.id,
                    ChildKnowledgeState.knowledge_point_id
                    == ActivityKnowledgePoint.knowledge_point_id,
                ),
            )
            .outerjoin(
                CourseActivityProgress,
                and_(
                    CourseActivityProgress.enrollment_id == ChildCourseEnrollment.id,
                    CourseActivityProgress.activity_id == LearningActivity.id,
                ),
            )
            .where(
                ChildCourseEnrollment.child_id == child.id,
                ChildCourseEnrollment.status != "archived",
                Course.status != "archived",
                CourseUnit.status != "archived",
                LearningActivity.status != "archived",
            )
            .group_by(ChildCourseEnrollment.id, Course.id, CourseUnit.id)
            .order_by(ChildCourseEnrollment.path_order, CourseUnit.order_index)
        )
    ).all()
    courses: dict[uuid.UUID, GrowthTreeCourseResponse] = {}
    for (
        _enrollment,
        course,
        unit,
        activity_count,
        completed,
        total,
        touched,
        growing,
        familiar,
    ) in rows:
        branch = courses.get(course.id)
        if branch is None:
            branch = GrowthTreeCourseResponse(
                id=course.id,
                title=course.title,
                source_type=course.source_type,
                course_progress_percent=0,
                total=0,
                touched=0,
                growing=0,
                familiar=0,
                units=[],
            )
            courses[course.id] = branch
        branch.units.append(
            GrowthTreeUnitResponse(
                id=unit.id,
                title=unit.title,
                total=int(total),
                course_completed_activities=int(completed),
                course_activity_count=int(activity_count),
                touched=int(touched),
                growing=int(growing),
                familiar=int(familiar),
            )
        )
        branch.total += int(total)
        branch.touched += int(touched)
        branch.growing += int(growing)
        branch.familiar += int(familiar)
    for branch in courses.values():
        activity_total = sum(unit.course_activity_count for unit in branch.units)
        activity_completed = sum(unit.course_completed_activities for unit in branch.units)
        branch.course_progress_percent = (
            round(activity_completed * 100 / activity_total, 1) if activity_total else 0
        )
    reading_completed = int(
        await session.scalar(
            select(func.count())
            .select_from(ReadingSession)
            .where(
                ReadingSession.child_id == child.id,
                ReadingSession.status == "completed",
            )
        )
        or 0
    )
    reading_independent = int(
        await session.scalar(
            select(func.count())
            .select_from(ReadingSession)
            .where(
                ReadingSession.child_id == child.id,
                ReadingSession.status == "completed",
                ReadingSession.reading_mode == "independent",
            )
        )
        or 0
    )
    science_completed = int(
        await session.scalar(
            select(func.count())
            .select_from(ExperimentSession)
            .where(
                ExperimentSession.child_id == child.id,
                ExperimentSession.status == "completed",
            )
        )
        or 0
    )
    science_questions = int(
        await session.scalar(
            select(func.count())
            .select_from(ExperimentEvidence)
            .where(
                ExperimentEvidence.child_id == child.id,
                ExperimentEvidence.evidence_type == "question_asked",
            )
        )
        or 0
    )
    return GrowthTreeResponse(
        child_id=child.id,
        projection_version=GROWTH_TREE_VERSION,
        mastery_mapping={
            "unlearned": "等待种下",
            "introduced": "种下种子",
            "recognizing": "正在发芽",
            "proficient": "长出新叶",
            "stable": "已经很熟悉",
        },
        chinese=list(courses.values()),
        reading=GrowthTreeDomainResponse(
            completed=reading_completed, independent=reading_independent
        ),
        science=GrowthTreeDomainResponse(completed=science_completed, questions=science_questions),
    )


async def reward_settings_response(
    session: AsyncSession, family_id: uuid.UUID
) -> RewardSettingsResponse:
    settings = await ensure_reward_settings(session, family_id)
    goals = list(
        await session.scalars(
            select(FamilyRewardGoal)
            .where(FamilyRewardGoal.family_id == family_id)
            .order_by(FamilyRewardGoal.required_stars, FamilyRewardGoal.created_at)
        )
    )
    await session.commit()
    return RewardSettingsResponse(
        family_id=family_id,
        stars_enabled=settings.stars_enabled,
        goals=[RewardGoalResponse.model_validate(item) for item in goals],
    )
