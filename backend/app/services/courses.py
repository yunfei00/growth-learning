"""Course ownership, path, progress, and canonical-evidence services."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityKnowledgePoint,
    CatalogRelease,
    ChildCourseEnrollment,
    ChildKnowledgeState,
    ChineseCharacter,
    Course,
    CourseActivityProgress,
    CourseSourceType,
    CourseStatus,
    CourseUnit,
    DailyLearningPlan,
    DailyPlanItem,
    DailyPlanItemKind,
    DailyPlanStatus,
    EnrollmentStatus,
    KnowledgePoint,
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
    CoursePointResponse,
    CourseResponse,
    CourseUnitResponse,
    EnrollmentResponse,
    PathCopyResponse,
)
from app.services.mastery import recompute_child_knowledge_state
from app.services.review_planning import recompute_review_schedule


async def _teacher_profile(session: AsyncSession, user_id: uuid.UUID) -> TeacherProfile | None:
    return await session.scalar(select(TeacherProfile).where(TeacherProfile.user_id == user_id))


async def visible_courses(
    session: AsyncSession, child_id: uuid.UUID, family_id: uuid.UUID
) -> list[Course]:
    teacher_ids = select(TeacherChildRelation.teacher_id).where(
        TeacherChildRelation.child_id == child_id,
        TeacherChildRelation.status == TeacherRelationStatus.ACTIVE,
    )
    return list(
        (
            await session.scalars(
                select(Course)
                .where(
                    Course.status != CourseStatus.ARCHIVED,
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
                .order_by(Course.source_type, Course.created_at, Course.id)
            )
        ).all()
    )


async def _course_is_visible(
    session: AsyncSession, course: Course, child_id: uuid.UUID, family_id: uuid.UUID
) -> bool:
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
    if payload.source_type == CourseSourceType.TEACHER and teacher_id is None:
        raise ValueError("Teacher course requires an active teacher profile")
    if payload.source_type != CourseSourceType.TEACHER and family_id is None:
        raise ValueError("Family course requires a family owner")
    point_ids = {
        point.knowledge_point_id
        for unit in payload.units
        for activity in unit.activities
        for point in activity.knowledge_points
    }
    existing = set(
        (
            await session.scalars(select(KnowledgePoint.id).where(KnowledgePoint.id.in_(point_ids)))
        ).all()
    )
    if existing != point_ids:
        raise ValueError("One or more canonical knowledge points do not exist")
    course = Course(
        subject="chinese",
        title=payload.title.strip(),
        description=payload.description,
        source_type=payload.source_type,
        family_id=family_id,
        teacher_id=teacher_id,
        created_by_user_id=actor_user_id,
        recommended_age_min=payload.recommended_age_min,
        recommended_age_max=payload.recommended_age_max,
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
                    )
                )
    await session.commit()
    return course


async def teacher_courses(session: AsyncSession, user_id: uuid.UUID) -> list[Course]:
    profile = await _teacher_profile(session, user_id)
    if profile is None:
        raise LookupError("Teacher mode is not enabled")
    return list(
        (
            await session.scalars(
                select(Course)
                .where(Course.teacher_id == profile.id)
                .order_by(Course.created_at.desc())
            )
        ).all()
    )


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
    all_point_levels: dict[uuid.UUID, str] = {}
    if child_id is not None:
        all_point_levels = dict(
            (
                await session.execute(
                    select(
                        ChildKnowledgeState.knowledge_point_id,
                        ChildKnowledgeState.mastery_level,
                    ).where(ChildKnowledgeState.child_id == child_id)
                )
            ).all()
        )
    for unit in units:
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
        unit_point_ids: set[uuid.UUID] = set()
        unit_completed = 0
        for activity in activities:
            mappings = list(
                (
                    await session.execute(
                        select(ActivityKnowledgePoint, ChineseCharacter)
                        .join(
                            ChineseCharacter,
                            ChineseCharacter.knowledge_point_id
                            == ActivityKnowledgePoint.knowledge_point_id,
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
            unit_point_ids.update(mapping.knowledge_point_id for mapping, _ in mappings)
            activity_responses.append(
                CourseActivityResponse(
                    id=activity.id,
                    title=activity.title,
                    activity_type=activity.activity_type,
                    instructions=activity.instructions,
                    order_index=activity.order_index,
                    status=activity.status,
                    progress_status=progress_status,
                    points=[
                        CoursePointResponse(
                            knowledge_point_id=mapping.knowledge_point_id,
                            character=character.character,
                            pinyin=character.pinyin,
                            role=mapping.role,
                            order_index=mapping.order_index,
                            mastery_level=all_point_levels.get(
                                mapping.knowledge_point_id, MasteryLevel.UNLEARNED
                            ),
                        )
                        for mapping, character in mappings
                    ],
                )
            )
        levels = [
            all_point_levels.get(point_id, MasteryLevel.UNLEARNED) for point_id in unit_point_ids
        ]
        introduced = sum(level != MasteryLevel.UNLEARNED for level in levels)
        stable = sum(level == MasteryLevel.STABLE for level in levels)
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
                activities=activity_responses,
            )
        )
        total_activities += len(activities)
        total_completed += unit_completed
    unique_points = {
        point.knowledge_point_id
        for unit in unit_responses
        for activity in unit.activities
        for point in activity.points
    }
    course_levels = [
        all_point_levels.get(point_id, MasteryLevel.UNLEARNED) for point_id in unique_points
    ]
    introduced_count = sum(level != MasteryLevel.UNLEARNED for level in course_levels)
    stable_count = sum(level == MasteryLevel.STABLE for level in course_levels)
    return CourseResponse(
        id=course.id,
        subject=course.subject,
        title=course.title,
        description=course.description,
        source_type=course.source_type,
        status=course.status,
        version=course.version,
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
            status=status,
            path_order=path_order,
            started_at=now if status == EnrollmentStatus.ACTIVE else None,
            settings={},
        )
        session.add(enrollment)
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
                LearningActivity.activity_type.in_(["character_learning", "character_review"]),
            )
        )
    ).one_or_none()
    if row is None:
        raise LookupError("Active course activity not found")
    enrollment, activity = row
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
                activity_type=(
                    LearningActivityType.RELEARNED
                    if point_id in existing
                    else LearningActivityType.INTRODUCED
                ),
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
