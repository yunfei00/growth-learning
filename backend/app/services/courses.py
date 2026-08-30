"""Course ownership, path, progress, and canonical-evidence services."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityKnowledgePoint,
    ActivityType,
    CatalogRelease,
    ChildCourseEnrollment,
    ChildKnowledgeState,
    ChineseCharacter,
    Course,
    CourseActivityProgress,
    CourseLesson,
    CoursePlatformEvent,
    CourseSourceType,
    CourseStatus,
    CourseUnit,
    CurriculumRelease,
    CurriculumReleaseStatus,
    DailyLearningPlan,
    DailyPlanItem,
    DailyPlanItemKind,
    DailyPlanStatus,
    EnrollmentStatus,
    KnowledgePoint,
    KnowledgeStatus,
    LearningActivity,
    LearningActivityType,
    LearningRecord,
    LearningSession,
    MasteryLevel,
    SessionStatus,
    TeacherChildRelation,
    TeacherProfile,
    TeacherRelationStatus,
)
from app.schemas.course import (
    CatalogReleaseResponse,
    CourseActivityCompletionResponse,
    CourseActivityResponse,
    CourseCreate,
    CourseLessonResponse,
    CoursePointResponse,
    CourseResponse,
    CourseUnitResponse,
    EnrollmentResponse,
    PathCopyResponse,
)
from app.services.mastery import mastery_policy_for_type, recompute_child_knowledge_state
from app.services.review_planning import recompute_review_schedule


@dataclass(frozen=True)
class ActivityEvidenceHandler:
    """Translate a course activity into canonical, append-only learning evidence."""

    activity_type: ActivityType
    first_evidence_type: LearningActivityType
    repeat_evidence_type: LearningActivityType

    def evidence_type(self, *, has_prior_evidence: bool) -> LearningActivityType:
        return self.repeat_evidence_type if has_prior_evidence else self.first_evidence_type


class ActivityHandlerRegistry:
    """Explicit boundary between course orchestration and evidence semantics."""

    def __init__(self, handlers: tuple[ActivityEvidenceHandler, ...]) -> None:
        self._handlers = {handler.activity_type.value: handler for handler in handlers}

    @property
    def supported_activity_types(self) -> tuple[str, ...]:
        return tuple(self._handlers)

    def resolve(self, activity_type: str) -> ActivityEvidenceHandler | None:
        return self._handlers.get(activity_type)


ACTIVITY_HANDLER_REGISTRY = ActivityHandlerRegistry(
    (
        ActivityEvidenceHandler(
            ActivityType.CHARACTER_LEARNING,
            LearningActivityType.INTRODUCED,
            LearningActivityType.RELEARNED,
        ),
        ActivityEvidenceHandler(
            ActivityType.CHARACTER_REVIEW,
            LearningActivityType.INTRODUCED,
            LearningActivityType.RELEARNED,
        ),
        ActivityEvidenceHandler(
            ActivityType.KNOWLEDGE_LEARNING,
            LearningActivityType.INTRODUCED,
            LearningActivityType.REVIEWED,
        ),
        ActivityEvidenceHandler(
            ActivityType.GUIDED_PRACTICE,
            LearningActivityType.GUIDED_PRACTICE,
            LearningActivityType.GUIDED_PRACTICE,
        ),
        ActivityEvidenceHandler(
            ActivityType.INDEPENDENT_PRACTICE,
            LearningActivityType.INDEPENDENT_PRACTICE,
            LearningActivityType.INDEPENDENT_PRACTICE,
        ),
        ActivityEvidenceHandler(
            ActivityType.KNOWLEDGE_REVIEW,
            LearningActivityType.REVIEWED,
            LearningActivityType.REVIEWED,
        ),
    )
)


async def _teacher_profile(session: AsyncSession, user_id: uuid.UUID) -> TeacherProfile | None:
    return await session.scalar(select(TeacherProfile).where(TeacherProfile.user_id == user_id))


async def visible_courses(
    session: AsyncSession,
    child_id: uuid.UUID,
    family_id: uuid.UUID,
    subject: str | None = None,
    grade_level: int | None = None,
    semester: str | None = None,
    education_stage: str | None = None,
) -> list[Course]:
    enrolled_course_ids = select(ChildCourseEnrollment.course_id).where(
        ChildCourseEnrollment.child_id == child_id
    )
    teacher_ids = select(TeacherChildRelation.teacher_id).where(
        TeacherChildRelation.child_id == child_id,
        TeacherChildRelation.status == TeacherRelationStatus.ACTIVE,
    )
    query = select(Course).where(
        or_(
            Course.status == CourseStatus.ENABLED,
            Course.id.in_(enrolled_course_ids),
        ),
        or_(
            Course.curriculum_release_id.is_(None),
            Course.curriculum_release_id.in_(
                select(CurriculumRelease.id).where(
                    CurriculumRelease.status == CurriculumReleaseStatus.PUBLISHED
                )
            ),
            and_(
                Course.id.in_(enrolled_course_ids),
                Course.curriculum_release_id.in_(
                    select(CurriculumRelease.id).where(
                        CurriculumRelease.status == CurriculumReleaseStatus.ARCHIVED
                    )
                ),
            ),
        ),
        or_(
            Course.source_type == CourseSourceType.SYSTEM,
            and_(
                Course.source_type.in_(
                    [
                        CourseSourceType.FAMILY,
                        CourseSourceType.TEXTBOOK_REFERENCE,
                    ]
                ),
                Course.family_id == family_id,
            ),
            and_(
                Course.source_type == CourseSourceType.TEACHER,
                Course.teacher_id.in_(teacher_ids),
            ),
        ),
    )
    if subject is not None:
        query = query.where(Course.subject == subject)
    if grade_level is not None:
        query = query.where(Course.grade_level == grade_level)
    if semester is not None:
        query = query.where(Course.semester == semester)
    if education_stage is not None:
        query = query.where(Course.education_stage == education_stage)
    return list(
        (
            await session.scalars(
                query.order_by(Course.subject, Course.source_type, Course.created_at, Course.id)
            )
        ).all()
    )


async def _course_is_visible(
    session: AsyncSession, course: Course, child_id: uuid.UUID, family_id: uuid.UUID
) -> bool:
    existing_enrollment = await _course_enrollment(session, child_id, course.id)
    if course.status != CourseStatus.ENABLED and existing_enrollment is None:
        return False
    if course.curriculum_release_id is not None:
        release_status = await session.scalar(
            select(CurriculumRelease.status).where(
                CurriculumRelease.id == course.curriculum_release_id
            )
        )
        if release_status != CurriculumReleaseStatus.PUBLISHED and existing_enrollment is None:
            return False
    if course.source_type == CourseSourceType.SYSTEM:
        return True
    if course.source_type in (
        CourseSourceType.FAMILY,
        CourseSourceType.TEXTBOOK_REFERENCE,
    ):
        return course.family_id == family_id
    return bool(
        await session.scalar(
            select(TeacherChildRelation.id).where(
                TeacherChildRelation.teacher_id == course.teacher_id,
                TeacherChildRelation.child_id == child_id,
                TeacherChildRelation.status == TeacherRelationStatus.ACTIVE,
            )
        )
    )


async def create_course(
    session: AsyncSession,
    payload: CourseCreate,
    actor_user_id: uuid.UUID,
    *,
    family_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
) -> Course:
    if payload.source_type == CourseSourceType.SYSTEM:
        if family_id is not None or teacher_id is not None:
            raise ValueError("System course cannot have a family or teacher owner")
    elif payload.source_type == CourseSourceType.TEACHER and teacher_id is None:
        raise ValueError("Teacher course requires an active teacher profile")
    elif payload.source_type != CourseSourceType.TEACHER and family_id is None:
        raise ValueError("Family course requires a family owner")
    point_ids = {
        point.knowledge_point_id
        for unit in payload.units
        for activity in unit.activities
        for point in activity.knowledge_points
    }
    point_rows = list(
        (
            await session.execute(
                select(KnowledgePoint.id, KnowledgePoint.subject).where(
                    KnowledgePoint.id.in_(point_ids),
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                )
            )
        ).all()
    )
    if {row.id for row in point_rows} != point_ids:
        raise ValueError("One or more active canonical knowledge points do not exist")
    mismatched = [row.id for row in point_rows if row.subject != payload.subject]
    if mismatched:
        raise ValueError("Course subject must match every linked knowledge point subject")
    course = Course(
        subject=payload.subject,
        title=payload.title.strip(),
        description=payload.description,
        source_type=payload.source_type,
        family_id=family_id,
        teacher_id=teacher_id,
        created_by_user_id=actor_user_id,
        recommended_age_min=payload.recommended_age_min,
        recommended_age_max=payload.recommended_age_max,
        education_stage=payload.education_stage,
        grade_level=payload.grade_level,
        semester=payload.semester,
        status=CourseStatus.ENABLED,
        version=1,
        reference_metadata=payload.reference_metadata,
    )
    session.add(course)
    await session.flush()
    for unit_order, unit_payload in enumerate(payload.units):
        unit = CourseUnit(
            course_id=course.id,
            title=unit_payload.title.strip(),
            description=unit_payload.description,
            order_index=unit_order,
            status=CourseStatus.ENABLED,
        )
        session.add(unit)
        await session.flush()
        for activity_order, activity_payload in enumerate(unit_payload.activities):
            activity = LearningActivity(
                course_unit_id=unit.id,
                activity_type=activity_payload.activity_type,
                title=activity_payload.title.strip(),
                instructions=activity_payload.instructions,
                order_index=activity_order,
                status=CourseStatus.ENABLED,
                content_metadata={},
            )
            session.add(activity)
            await session.flush()
            for point_order, point_payload in enumerate(activity_payload.knowledge_points):
                session.add(
                    ActivityKnowledgePoint(
                        activity_id=activity.id,
                        knowledge_point_id=point_payload.knowledge_point_id,
                        role=point_payload.role,
                        order_index=point_order,
                        reference_code=point_payload.reference_code,
                        curriculum_metadata=point_payload.curriculum_metadata,
                    )
                )
    await session.commit()
    return course


async def teacher_courses(
    session: AsyncSession, user_id: uuid.UUID, subject: str | None = None
) -> list[Course]:
    profile = await _teacher_profile(session, user_id)
    if profile is None:
        raise LookupError("Teacher mode is not enabled")
    query = select(Course).where(Course.teacher_id == profile.id)
    if subject is not None:
        query = query.where(Course.subject == subject)
    return list((await session.scalars(query.order_by(Course.created_at.desc()))).all())


async def _course_enrollment(
    session: AsyncSession, child_id: uuid.UUID, course_id: uuid.UUID
) -> ChildCourseEnrollment | None:
    return await session.scalar(
        select(ChildCourseEnrollment).where(
            ChildCourseEnrollment.child_id == child_id,
            ChildCourseEnrollment.course_id == course_id,
        )
    )


async def course_response(
    session: AsyncSession, course: Course, child_id: uuid.UUID | None
) -> CourseResponse:
    enrollment = (
        await _course_enrollment(session, child_id, course.id) if child_id is not None else None
    )
    units = list(
        (
            await session.scalars(
                select(CourseUnit)
                .where(CourseUnit.course_id == course.id)
                .order_by(CourseUnit.order_index)
            )
        ).all()
    )
    unit_responses: list[CourseUnitResponse] = []
    total_activities = 0
    total_completed = 0
    all_point_states: dict[uuid.UUID, ChildKnowledgeState] = {}
    if child_id is not None:
        all_point_states = {
            state.knowledge_point_id: state
            for state in await session.scalars(
                select(ChildKnowledgeState).where(ChildKnowledgeState.child_id == child_id)
            )
        }
    for unit in units:
        lessons = list(
            (
                await session.scalars(
                    select(CourseLesson)
                    .where(CourseLesson.course_unit_id == unit.id)
                    .order_by(CourseLesson.order_index)
                )
            ).all()
        )
        activities = list(
            (
                await session.scalars(
                    select(LearningActivity)
                    .where(LearningActivity.course_unit_id == unit.id)
                    .order_by(LearningActivity.order_index)
                )
            ).all()
        )
        activity_responses: list[CourseActivityResponse] = []
        unit_completed = 0
        for activity in activities:
            mappings = list(
                (
                    await session.execute(
                        select(ActivityKnowledgePoint, KnowledgePoint, ChineseCharacter)
                        .join(
                            KnowledgePoint,
                            KnowledgePoint.id == ActivityKnowledgePoint.knowledge_point_id,
                        )
                        .outerjoin(
                            ChineseCharacter,
                            ChineseCharacter.knowledge_point_id == KnowledgePoint.id,
                        )
                        .where(ActivityKnowledgePoint.activity_id == activity.id)
                        .order_by(ActivityKnowledgePoint.order_index)
                    )
                ).all()
            )
            progress = None
            if enrollment is not None:
                progress = await session.scalar(
                    select(CourseActivityProgress).where(
                        CourseActivityProgress.enrollment_id == enrollment.id,
                        CourseActivityProgress.activity_id == activity.id,
                    )
                )
            progress_status = progress.status if progress else "pending"
            unit_completed += progress_status == "completed"
            point_responses: list[CoursePointResponse] = []
            for mapping, point, character in mappings:
                policy = mastery_policy_for_type(point.type)
                state = all_point_states.get(point.id) if policy is not None else None
                point_responses.append(
                    CoursePointResponse(
                        mapping_id=mapping.id,
                        knowledge_point_id=point.id,
                        title=point.title,
                        subject=point.subject,
                        knowledge_type=point.type,
                        character=character.character if character is not None else None,
                        pinyin=character.pinyin if character is not None else None,
                        role=mapping.role,
                        order_index=mapping.order_index,
                        reference_code=mapping.reference_code,
                        curriculum_metadata=mapping.curriculum_metadata,
                        mastery_level=(
                            state.mastery_level
                            if state is not None
                            else MasteryLevel.UNLEARNED
                            if policy is not None
                            else None
                        ),
                        mastery_policy_key=policy.key if policy is not None else None,
                        projection_status=("configured" if policy is not None else "unavailable"),
                    )
                )
            activity_responses.append(
                CourseActivityResponse(
                    id=activity.id,
                    title=activity.title,
                    activity_type=activity.activity_type,
                    instructions=activity.instructions,
                    order_index=activity.order_index,
                    status=activity.status,
                    lesson_id=activity.lesson_id,
                    progress_status=progress_status,
                    points=point_responses,
                )
            )
        unit_points = [point for activity in activity_responses for point in activity.points]
        levels = [
            point.mastery_level
            for point in unit_points
            if point.projection_status == "configured" and point.mastery_level is not None
        ]
        unavailable_count = len(
            {
                point.knowledge_point_id
                for point in unit_points
                if point.projection_status == "unavailable"
            }
        )
        introduced = sum(level != MasteryLevel.UNLEARNED for level in levels)
        stable = sum(level == MasteryLevel.STABLE for level in levels)
        lesson_responses = [
            CourseLessonResponse(
                id=lesson.id,
                title=lesson.title,
                description=lesson.description,
                order_index=lesson.order_index,
                estimated_minutes=lesson.estimated_minutes,
                status=lesson.status,
                metadata_json=lesson.metadata_json,
                activity_count=len(
                    [activity for activity in activity_responses if activity.lesson_id == lesson.id]
                ),
                completed_activities=len(
                    [
                        activity
                        for activity in activity_responses
                        if activity.lesson_id == lesson.id
                        and activity.progress_status == "completed"
                    ]
                ),
                activities=[
                    activity for activity in activity_responses if activity.lesson_id == lesson.id
                ],
            )
            for lesson in lessons
        ]
        unit_responses.append(
            CourseUnitResponse(
                id=unit.id,
                title=unit.title,
                description=unit.description,
                order_index=unit.order_index,
                status=unit.status,
                activity_count=len(activities),
                completed_activities=unit_completed,
                introduced_count=introduced,
                stable_count=stable,
                unlearned_count=len(levels) - introduced,
                projection_unavailable_count=unavailable_count,
                lessons=lesson_responses,
                activities=activity_responses,
            )
        )
        total_activities += len(activities)
        total_completed += unit_completed
    unique_points = {
        point.knowledge_point_id: point
        for unit in unit_responses
        for activity in unit.activities
        for point in activity.points
    }
    course_levels = [
        point.mastery_level
        for point in unique_points.values()
        if point.projection_status == "configured" and point.mastery_level is not None
    ]
    projection_unavailable_count = sum(
        point.projection_status == "unavailable" for point in unique_points.values()
    )
    introduced_count = sum(level != MasteryLevel.UNLEARNED for level in course_levels)
    stable_count = sum(level == MasteryLevel.STABLE for level in course_levels)
    release = (
        await session.get(CurriculumRelease, course.curriculum_release_id)
        if course.curriculum_release_id is not None
        else None
    )
    stage_labels = {
        "foundation": "幼儿 / 启蒙",
        "primary": "小学",
        "junior_middle": "初中",
    }
    semester_labels = {
        "full_year": "全年",
        "semester_1": "上学期",
        "semester_2": "下学期",
    }
    grade_labels = {
        1: "一年级",
        2: "二年级",
        3: "三年级",
        4: "四年级",
        5: "五年级",
        6: "六年级",
        7: "七年级",
        8: "八年级",
        9: "九年级",
    }
    return CourseResponse(
        id=course.id,
        subject=course.subject,
        title=course.title,
        description=course.description,
        source_type=course.source_type,
        status=course.status,
        version=course.version,
        education_stage=course.education_stage,
        education_stage_label=stage_labels[course.education_stage],
        grade_level=course.grade_level,
        grade_level_label=grade_labels.get(course.grade_level, "启蒙"),
        semester=course.semester,
        semester_label=semester_labels[course.semester],
        curriculum_key=course.curriculum_key,
        curriculum_version=course.curriculum_version,
        curriculum_release_id=course.curriculum_release_id,
        curriculum_release_status=release.status if release else None,
        recommended_age_min=course.recommended_age_min,
        recommended_age_max=course.recommended_age_max,
        reference_metadata=course.reference_metadata,
        enrollment_id=enrollment.id if enrollment else None,
        enrollment_status=enrollment.status if enrollment else None,
        path_order=enrollment.path_order if enrollment else None,
        activity_count=total_activities,
        completed_activities=total_completed,
        progress_percent=(
            round(total_completed * 100 / total_activities, 1) if total_activities else 0
        ),
        introduced_count=introduced_count,
        stable_count=stable_count,
        unlearned_count=len(course_levels) - introduced_count,
        projection_unavailable_count=projection_unavailable_count,
        units=unit_responses,
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


async def enroll_child(
    session: AsyncSession,
    child_id: uuid.UUID,
    family_id: uuid.UUID,
    course_id: uuid.UUID,
    path_order: int,
    status: str,
) -> ChildCourseEnrollment:
    course = await session.get(Course, course_id)
    if course is None or not await _course_is_visible(session, course, child_id, family_id):
        raise LookupError("Course not found")
    enrollment = await _course_enrollment(session, child_id, course.id)
    now = datetime.now(UTC)
    if enrollment is None:
        enrollment = ChildCourseEnrollment(
            child_id=child_id,
            course_id=course.id,
            course_version=course.version,
            curriculum_release_id=course.curriculum_release_id,
            status=status,
            path_order=path_order,
            started_at=now if status == EnrollmentStatus.ACTIVE else None,
            settings={},
        )
        session.add(enrollment)
        await session.flush()
        if status == EnrollmentStatus.ACTIVE:
            session.add(
                CoursePlatformEvent(
                    child_id=child_id,
                    enrollment_id=enrollment.id,
                    event_type="course_started",
                    occurred_at=now,
                    metadata_json={"course_id": str(course.id)},
                )
            )
    else:
        enrollment.status = status
        enrollment.path_order = path_order
        if status == EnrollmentStatus.ACTIVE and enrollment.started_at is None:
            enrollment.started_at = now
    await session.commit()
    return enrollment


async def enrollment_response(
    session: AsyncSession, enrollment: ChildCourseEnrollment
) -> EnrollmentResponse:
    course = await session.get(Course, enrollment.course_id)
    assert course is not None
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(LearningActivity)
            .join(CourseUnit, CourseUnit.id == LearningActivity.course_unit_id)
            .where(CourseUnit.course_id == course.id)
        )
        or 0
    )
    completed = int(
        await session.scalar(
            select(func.count())
            .select_from(CourseActivityProgress)
            .where(
                CourseActivityProgress.enrollment_id == enrollment.id,
                CourseActivityProgress.status == "completed",
            )
        )
        or 0
    )
    return EnrollmentResponse(
        id=enrollment.id,
        child_id=enrollment.child_id,
        course_id=course.id,
        course_title=course.title,
        course_version=enrollment.course_version,
        curriculum_release_id=enrollment.curriculum_release_id,
        curriculum_version=course.curriculum_version,
        status=enrollment.status,
        path_order=enrollment.path_order,
        started_at=enrollment.started_at,
        completed_at=enrollment.completed_at,
        progress_percent=round(completed * 100 / total, 1) if total else 0,
    )


async def copy_course_path(
    session: AsyncSession, source_child_id: uuid.UUID, target_child_id: uuid.UUID
) -> PathCopyResponse:
    source = list(
        (
            await session.scalars(
                select(ChildCourseEnrollment).where(
                    ChildCourseEnrollment.child_id == source_child_id,
                    ChildCourseEnrollment.status != EnrollmentStatus.ARCHIVED,
                )
            )
        ).all()
    )
    copied = 0
    for item in source:
        target = await _course_enrollment(session, target_child_id, item.course_id)
        if target is None:
            session.add(
                ChildCourseEnrollment(
                    child_id=target_child_id,
                    course_id=item.course_id,
                    course_version=item.course_version,
                    curriculum_release_id=item.curriculum_release_id,
                    status=EnrollmentStatus.PLANNED,
                    path_order=item.path_order,
                    settings=dict(item.settings),
                )
            )
            copied += 1
        else:
            target.path_order = item.path_order
            target.settings = dict(item.settings)
    await session.commit()
    return PathCopyResponse(copied_enrollments=copied)


async def complete_character_activity(
    session: AsyncSession,
    child_id: uuid.UUID,
    activity_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> CourseActivityCompletionResponse:
    """Complete any registered evidence-producing course activity.

    The legacy name is kept for API compatibility. Unsupported activities remain
    viewable but cannot accidentally invent learning evidence.
    """
    row = (
        await session.execute(
            select(ChildCourseEnrollment, LearningActivity)
            .join(Course, Course.id == ChildCourseEnrollment.course_id)
            .join(CourseUnit, CourseUnit.course_id == Course.id)
            .join(LearningActivity, LearningActivity.course_unit_id == CourseUnit.id)
            .where(
                ChildCourseEnrollment.child_id == child_id,
                ChildCourseEnrollment.status == EnrollmentStatus.ACTIVE,
                LearningActivity.id == activity_id,
                LearningActivity.activity_type.in_(
                    ACTIVITY_HANDLER_REGISTRY.supported_activity_types
                ),
            )
        )
    ).one_or_none()
    if row is None:
        raise LookupError("Active course activity not found")
    enrollment, activity = row
    handler = ACTIVITY_HANDLER_REGISTRY.resolve(activity.activity_type)
    if handler is None:
        raise LookupError("Activity does not produce canonical learning evidence")
    progress = await session.scalar(
        select(CourseActivityProgress).where(
            CourseActivityProgress.enrollment_id == enrollment.id,
            CourseActivityProgress.activity_id == activity.id,
        )
    )
    if progress is not None and progress.status == "completed":
        count = int(
            await session.scalar(
                select(func.count())
                .select_from(LearningRecord)
                .where(LearningRecord.session_id == progress.learning_session_id)
            )
            or 0
        )
        assert progress.learning_session_id is not None
        return CourseActivityCompletionResponse(
            activity_id=activity.id,
            progress_status=progress.status,
            learning_session_id=progress.learning_session_id,
            learning_records_created=count,
        )
    now = datetime.now(UTC)
    learning_session = LearningSession(
        child_id=child_id,
        actor_user_id=actor_user_id,
        status=SessionStatus.COMPLETED,
        source="course",
        started_at=now,
        completed_at=now,
    )
    session.add(learning_session)
    await session.flush()
    point_ids = list(
        (
            await session.scalars(
                select(ActivityKnowledgePoint.knowledge_point_id)
                .where(ActivityKnowledgePoint.activity_id == activity.id)
                .order_by(ActivityKnowledgePoint.order_index)
            )
        ).all()
    )
    existing = set(
        (
            await session.scalars(
                select(LearningRecord.knowledge_point_id).where(
                    LearningRecord.child_id == child_id,
                    LearningRecord.knowledge_point_id.in_(point_ids),
                )
            )
        ).all()
    )
    for point_id in point_ids:
        session.add(
            LearningRecord(
                session_id=learning_session.id,
                child_id=child_id,
                knowledge_point_id=point_id,
                actor_user_id=actor_user_id,
                activity_type=handler.evidence_type(has_prior_evidence=point_id in existing),
                source="course",
                learned_at=now,
            )
        )
    daily_plan = await session.scalar(
        select(DailyLearningPlan)
        .where(DailyLearningPlan.child_id == child_id)
        .order_by(DailyLearningPlan.plan_date.desc())
    )
    if daily_plan is not None:
        daily_items = list(
            (
                await session.scalars(
                    select(DailyPlanItem).where(
                        DailyPlanItem.daily_plan_id == daily_plan.id,
                        DailyPlanItem.item_kind == DailyPlanItemKind.NEW,
                        DailyPlanItem.status == "pending",
                        DailyPlanItem.knowledge_point_id.in_(point_ids),
                    )
                )
            ).all()
        )
        for daily_item in daily_items:
            daily_item.status = "completed"
            daily_item.completed_at = now
        daily_plan.new_completed_count += len(daily_items)
        daily_plan.status = (
            DailyPlanStatus.COMPLETED
            if daily_plan.new_completed_count >= daily_plan.recommended_new_count
            and daily_plan.review_completed_count >= daily_plan.review_count
            else DailyPlanStatus.IN_PROGRESS
        )
    if progress is None:
        progress = CourseActivityProgress(
            enrollment_id=enrollment.id,
            activity_id=activity.id,
        )
        session.add(progress)
    progress.status = "completed"
    progress.learning_session_id = learning_session.id
    progress.started_at = progress.started_at or now
    progress.completed_at = now
    session.add(
        CoursePlatformEvent(
            child_id=child_id,
            enrollment_id=enrollment.id,
            event_type="activity_completed",
            occurred_at=now,
            metadata_json={"activity_id": str(activity.id)},
        )
    )
    await session.flush()
    for point_id in point_ids:
        await recompute_child_knowledge_state(session, child_id, point_id)
        await recompute_review_schedule(session, child_id, point_id)
    await session.commit()
    return CourseActivityCompletionResponse(
        activity_id=activity.id,
        progress_status=progress.status,
        learning_session_id=learning_session.id,
        learning_records_created=len(point_ids),
    )


async def current_catalog(session: AsyncSession) -> CatalogReleaseResponse | None:
    release = await session.scalar(
        select(CatalogRelease).where(CatalogRelease.is_current.is_(True))
    )
    if release is None:
        return None
    return CatalogReleaseResponse(
        catalog_version=release.catalog_version,
        item_count=release.item_count,
        source_type=release.source_type,
        source_name=release.source_name,
        source_reference=release.source_reference,
        license=release.license,
        imported_at=release.imported_at,
        is_current=release.is_current,
        metadata=release.metadata_json,
    )
