"""Curriculum release workflow, validation, builder, and portable JSON operations."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityKnowledgePoint,
    Course,
    CourseLesson,
    CourseSourceType,
    CourseStatus,
    CourseUnit,
    CurriculumRelease,
    CurriculumReleaseStatus,
    EnglishItem,
    KnowledgePoint,
    KnowledgeStatus,
    LearningActivity,
    MathProblemTemplate,
    PinyinItem,
)
from app.schemas.curriculum import (
    CurriculumActivityCreate,
    CurriculumDocument,
    CurriculumImportReport,
    CurriculumLessonCreate,
    CurriculumMappingCreate,
    CurriculumNewVersionRequest,
    CurriculumNodeUpdate,
    CurriculumReleaseCreate,
    CurriculumReleaseResponse,
    CurriculumReleaseUpdate,
    CurriculumUnitCreate,
    CurriculumValidationIssue,
    CurriculumValidationReport,
)
from app.services.courses import course_response
from app.services.platform_access import add_platform_audit

STAGE_LABELS = {
    "foundation": "幼儿 / 启蒙",
    "primary": "小学",
    "junior_middle": "初中",
}
GRADE_LABELS = {
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
SEMESTER_LABELS = {
    "full_year": "全年",
    "semester_1": "上学期",
    "semester_2": "下学期",
}


async def _course_for_release(session: AsyncSession, release_id: uuid.UUID) -> Course:
    course = await session.scalar(select(Course).where(Course.curriculum_release_id == release_id))
    if course is None:
        raise LookupError("Curriculum release course not found")
    return course


async def _release_for_course(session: AsyncSession, course_id: uuid.UUID) -> CurriculumRelease:
    release = await session.scalar(
        select(CurriculumRelease)
        .join(Course, Course.curriculum_release_id == CurriculumRelease.id)
        .where(Course.id == course_id)
    )
    if release is None:
        raise LookupError("Curriculum release not found")
    return release


async def _release_for_unit(session: AsyncSession, unit_id: uuid.UUID) -> CurriculumRelease:
    release = await session.scalar(
        select(CurriculumRelease)
        .join(Course, Course.curriculum_release_id == CurriculumRelease.id)
        .join(CourseUnit, CourseUnit.course_id == Course.id)
        .where(CourseUnit.id == unit_id)
    )
    if release is None:
        raise LookupError("Curriculum unit not found")
    return release


async def _release_for_lesson(session: AsyncSession, lesson_id: uuid.UUID) -> CurriculumRelease:
    release = await session.scalar(
        select(CurriculumRelease)
        .join(Course, Course.curriculum_release_id == CurriculumRelease.id)
        .join(CourseUnit, CourseUnit.course_id == Course.id)
        .join(CourseLesson, CourseLesson.course_unit_id == CourseUnit.id)
        .where(CourseLesson.id == lesson_id)
    )
    if release is None:
        raise LookupError("Curriculum lesson not found")
    return release


async def _release_for_activity(session: AsyncSession, activity_id: uuid.UUID) -> CurriculumRelease:
    release = await session.scalar(
        select(CurriculumRelease)
        .join(Course, Course.curriculum_release_id == CurriculumRelease.id)
        .join(CourseUnit, CourseUnit.course_id == Course.id)
        .join(LearningActivity, LearningActivity.course_unit_id == CourseUnit.id)
        .where(LearningActivity.id == activity_id)
    )
    if release is None:
        raise LookupError("Curriculum activity not found")
    return release


async def curriculum_release_for_node(
    session: AsyncSession, node_type: str, node_id: uuid.UUID
) -> CurriculumRelease:
    resolvers = {
        "unit": _release_for_unit,
        "lesson": _release_for_lesson,
        "activity": _release_for_activity,
    }
    try:
        resolver = resolvers[node_type]
    except KeyError as error:
        raise ValueError("Unsupported curriculum node type") from error
    return await resolver(session, node_id)


def _require_draft(release: CurriculumRelease) -> None:
    if release.status != CurriculumReleaseStatus.DRAFT:
        raise ValueError("Only draft curriculum releases can change structure")


def _audit(
    session: AsyncSession,
    event_type: str,
    actor_user_id: uuid.UUID,
    release: CurriculumRelease,
    **metadata: object,
) -> None:
    add_platform_audit(
        session,
        event_type=event_type,
        actor_user_id=actor_user_id,
        metadata={
            "curriculum_release_id": str(release.id),
            "curriculum_key": release.curriculum_key,
            "release_version": release.release_version,
            **metadata,
        },
    )


async def create_curriculum_release(
    session: AsyncSession,
    payload: CurriculumReleaseCreate,
    actor_user_id: uuid.UUID,
    *,
    commit: bool = True,
) -> tuple[CurriculumRelease, Course]:
    existing = await session.scalar(
        select(CurriculumRelease.id).where(
            CurriculumRelease.curriculum_key == payload.curriculum_key,
            CurriculumRelease.release_version == payload.release_version,
        )
    )
    if existing is not None:
        raise ValueError("Curriculum release version already exists")
    release = CurriculumRelease(
        **payload.model_dump(),
        status=CurriculumReleaseStatus.DRAFT,
        created_by_user_id=actor_user_id,
        validation_snapshot={},
    )
    session.add(release)
    await session.flush()
    course = Course(
        subject=payload.subject,
        title=payload.title.strip(),
        description=payload.description,
        source_type=CourseSourceType.SYSTEM,
        created_by_user_id=actor_user_id,
        status=CourseStatus.DRAFT,
        version=1,
        education_stage=payload.education_stage,
        grade_level=payload.grade_level,
        semester=payload.semester,
        curriculum_key=payload.curriculum_key,
        curriculum_version=payload.release_version,
        curriculum_release_id=release.id,
        reference_metadata={"provenance_source_type": payload.source_type},
    )
    session.add(course)
    _audit(session, "course_created", actor_user_id, release)
    if commit:
        await session.commit()
    else:
        await session.flush()
    return release, course


async def update_curriculum_release(
    session: AsyncSession,
    release: CurriculumRelease,
    payload: CurriculumReleaseUpdate,
    actor_user_id: uuid.UUID,
) -> CurriculumRelease:
    _require_draft(release)
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        setattr(release, field, value)
    course = await _course_for_release(session, release.id)
    if "title" in values:
        course.title = values["title"]
    if "description" in values:
        course.description = values["description"]
    _audit(session, "course_updated", actor_user_id, release, fields=sorted(values))
    await session.commit()
    return release


async def release_response(
    session: AsyncSession, release: CurriculumRelease, *, include_course: bool = False
) -> CurriculumReleaseResponse:
    course = await _course_for_release(session, release.id)
    units = int(
        await session.scalar(
            select(func.count()).select_from(CourseUnit).where(CourseUnit.course_id == course.id)
        )
        or 0
    )
    lessons = int(
        await session.scalar(
            select(func.count())
            .select_from(CourseLesson)
            .join(CourseUnit, CourseUnit.id == CourseLesson.course_unit_id)
            .where(CourseUnit.course_id == course.id)
        )
        or 0
    )
    activities = int(
        await session.scalar(
            select(func.count())
            .select_from(LearningActivity)
            .join(CourseUnit, CourseUnit.id == LearningActivity.course_unit_id)
            .where(CourseUnit.course_id == course.id)
        )
        or 0
    )
    knowledge_points = int(
        await session.scalar(
            select(func.count(func.distinct(ActivityKnowledgePoint.knowledge_point_id)))
            .select_from(ActivityKnowledgePoint)
            .join(LearningActivity, LearningActivity.id == ActivityKnowledgePoint.activity_id)
            .join(CourseUnit, CourseUnit.id == LearningActivity.course_unit_id)
            .where(CourseUnit.course_id == course.id)
        )
        or 0
    )
    return CurriculumReleaseResponse(
        id=release.id,
        course_id=course.id,
        curriculum_key=release.curriculum_key,
        release_version=release.release_version,
        education_stage=release.education_stage,
        education_stage_label=STAGE_LABELS[release.education_stage],
        grade_level=release.grade_level,
        grade_level_label=GRADE_LABELS.get(release.grade_level, "启蒙"),
        semester=release.semester,
        semester_label=SEMESTER_LABELS[release.semester],
        subject=release.subject,
        title=release.title,
        description=release.description,
        status=release.status,
        source_type=release.source_type,
        source_name=release.source_name,
        source_reference=release.source_reference,
        license=release.license,
        copyright_notice=release.copyright_notice,
        created_by_user_id=release.created_by_user_id,
        reviewed_by_user_id=release.reviewed_by_user_id,
        published_by_user_id=release.published_by_user_id,
        created_at=release.created_at,
        reviewed_at=release.reviewed_at,
        published_at=release.published_at,
        archived_at=release.archived_at,
        change_summary=release.change_summary,
        validation_snapshot=release.validation_snapshot,
        metadata_json=release.metadata_json,
        unit_count=units,
        lesson_count=lessons,
        activity_count=activities,
        knowledge_point_count=knowledge_points,
        course=await course_response(session, course, None) if include_course else None,
    )


async def list_curriculum_releases(
    session: AsyncSession,
    *,
    education_stage: str | None = None,
    grade_level: int | None = None,
    semester: str | None = None,
    subject: str | None = None,
    status: str | None = None,
) -> list[CurriculumRelease]:
    filters = []
    for column, value in (
        (CurriculumRelease.education_stage, education_stage),
        (CurriculumRelease.grade_level, grade_level),
        (CurriculumRelease.semester, semester),
        (CurriculumRelease.subject, subject),
        (CurriculumRelease.status, status),
    ):
        if value is not None:
            filters.append(column == value)
    return list(
        (
            await session.scalars(
                select(CurriculumRelease)
                .where(*filters)
                .order_by(
                    CurriculumRelease.grade_level,
                    CurriculumRelease.semester,
                    CurriculumRelease.subject,
                    CurriculumRelease.created_at.desc(),
                )
            )
        ).all()
    )


async def add_curriculum_unit(
    session: AsyncSession,
    release: CurriculumRelease,
    payload: CurriculumUnitCreate,
    actor_user_id: uuid.UUID,
) -> CourseUnit:
    _require_draft(release)
    course = await _course_for_release(session, release.id)
    next_order = (
        int(
            await session.scalar(
                select(func.coalesce(func.max(CourseUnit.order_index), -1)).where(
                    CourseUnit.course_id == course.id
                )
            )
        )
        + 1
    )
    unit = CourseUnit(
        course_id=course.id,
        title=payload.title.strip(),
        description=payload.description,
        order_index=next_order,
        status=CourseStatus.DRAFT,
    )
    session.add(unit)
    _audit(session, "course_updated", actor_user_id, release, node_type="unit")
    await session.commit()
    return unit


async def add_curriculum_lesson(
    session: AsyncSession,
    unit: CourseUnit,
    payload: CurriculumLessonCreate,
    actor_user_id: uuid.UUID,
) -> CourseLesson:
    release = await _release_for_unit(session, unit.id)
    _require_draft(release)
    next_order = (
        int(
            await session.scalar(
                select(func.coalesce(func.max(CourseLesson.order_index), -1)).where(
                    CourseLesson.course_unit_id == unit.id
                )
            )
        )
        + 1
    )
    lesson = CourseLesson(
        course_unit_id=unit.id,
        title=payload.title.strip(),
        description=payload.description,
        estimated_minutes=payload.estimated_minutes,
        metadata_json=payload.metadata_json,
        order_index=next_order,
        status=CourseStatus.DRAFT,
    )
    session.add(lesson)
    _audit(session, "course_updated", actor_user_id, release, node_type="lesson")
    await session.commit()
    return lesson


async def add_curriculum_activity(
    session: AsyncSession,
    lesson: CourseLesson,
    payload: CurriculumActivityCreate,
    actor_user_id: uuid.UUID,
) -> LearningActivity:
    release = await _release_for_lesson(session, lesson.id)
    _require_draft(release)
    next_order = (
        int(
            await session.scalar(
                select(func.coalesce(func.max(LearningActivity.order_index), -1)).where(
                    LearningActivity.course_unit_id == lesson.course_unit_id
                )
            )
        )
        + 1
    )
    activity = LearningActivity(
        course_unit_id=lesson.course_unit_id,
        lesson_id=lesson.id,
        activity_type=payload.activity_type,
        title=payload.title.strip(),
        instructions=payload.instructions,
        content_metadata=payload.content_metadata,
        order_index=next_order,
        status=CourseStatus.DRAFT,
    )
    session.add(activity)
    _audit(session, "course_updated", actor_user_id, release, node_type="activity")
    await session.commit()
    return activity


async def add_curriculum_mapping(
    session: AsyncSession,
    activity: LearningActivity,
    payload: CurriculumMappingCreate,
    actor_user_id: uuid.UUID,
) -> ActivityKnowledgePoint:
    release = await _release_for_activity(session, activity.id)
    _require_draft(release)
    point = await session.get(KnowledgePoint, payload.knowledge_point_id)
    if point is None or point.status != KnowledgeStatus.ACTIVE:
        raise ValueError("Active canonical knowledge point not found")
    if point.subject != release.subject:
        raise ValueError("Course subject must match the linked knowledge point subject")
    existing = await session.scalar(
        select(ActivityKnowledgePoint.id).where(
            ActivityKnowledgePoint.activity_id == activity.id,
            ActivityKnowledgePoint.knowledge_point_id == point.id,
        )
    )
    if existing is not None:
        raise ValueError("Knowledge point is already linked to this activity")
    next_order = (
        int(
            await session.scalar(
                select(func.coalesce(func.max(ActivityKnowledgePoint.order_index), -1)).where(
                    ActivityKnowledgePoint.activity_id == activity.id
                )
            )
        )
        + 1
    )
    mapping = ActivityKnowledgePoint(
        activity_id=activity.id,
        knowledge_point_id=point.id,
        role=payload.role,
        order_index=next_order,
        reference_code=payload.reference_code,
        curriculum_metadata=payload.metadata_json,
    )
    session.add(mapping)
    _audit(session, "course_updated", actor_user_id, release, node_type="knowledge_mapping")
    await session.commit()
    return mapping


async def update_curriculum_node(
    session: AsyncSession,
    node_type: str,
    node_id: uuid.UUID,
    payload: CurriculumNodeUpdate,
    actor_user_id: uuid.UUID,
) -> object:
    model = {"unit": CourseUnit, "lesson": CourseLesson, "activity": LearningActivity}.get(
        node_type
    )
    if model is None:
        raise ValueError("Unsupported curriculum node type")
    node = await session.get(model, node_id)
    if node is None:
        raise LookupError("Curriculum node not found")
    if node_type == "unit":
        release = await _release_for_unit(session, node_id)
    elif node_type == "lesson":
        release = await _release_for_lesson(session, node_id)
    else:
        release = await _release_for_activity(session, node_id)
    _require_draft(release)
    values = payload.model_dump(exclude_unset=True)
    metadata = values.pop("metadata_json", None)
    if metadata is not None:
        target_field = "content_metadata" if node_type == "activity" else "metadata_json"
        setattr(node, target_field, metadata)
    for field, value in values.items():
        if hasattr(node, field):
            setattr(node, field, value)
    _audit(session, "course_updated", actor_user_id, release, node_type=node_type)
    await session.commit()
    return node


async def move_curriculum_node(
    session: AsyncSession,
    node_type: str,
    node_id: uuid.UUID,
    direction: str,
    actor_user_id: uuid.UUID,
) -> None:
    model = {"unit": CourseUnit, "lesson": CourseLesson, "activity": LearningActivity}.get(
        node_type
    )
    if model is None:
        raise ValueError("Unsupported curriculum node type")
    node = await session.get(model, node_id)
    if node is None:
        raise LookupError("Curriculum node not found")
    if node_type == "unit":
        release = await _release_for_unit(session, node_id)
        sibling_filter = CourseUnit.course_id == node.course_id
    elif node_type == "lesson":
        release = await _release_for_lesson(session, node_id)
        sibling_filter = CourseLesson.course_unit_id == node.course_unit_id
    else:
        release = await _release_for_activity(session, node_id)
        sibling_filter = LearningActivity.lesson_id == node.lesson_id
    _require_draft(release)
    comparator = (
        model.order_index < node.order_index
        if direction == "up"
        else model.order_index > node.order_index
    )
    ordering = model.order_index.desc() if direction == "up" else model.order_index.asc()
    sibling = await session.scalar(
        select(model).where(sibling_filter, comparator).order_by(ordering).limit(1)
    )
    if sibling is None:
        return
    if node_type == "activity":
        temporary = (
            int(
                await session.scalar(
                    select(func.coalesce(func.max(LearningActivity.order_index), -1)).where(
                        LearningActivity.course_unit_id == node.course_unit_id
                    )
                )
            )
            + 1
        )
    else:
        temporary = max(node.order_index, sibling.order_index) + 1
    old_order = node.order_index
    node.order_index = temporary
    await session.flush()
    sibling_order = sibling.order_index
    sibling.order_index = old_order
    await session.flush()
    node.order_index = sibling_order
    _audit(session, "course_updated", actor_user_id, release, node_type=node_type, action="move")
    await session.commit()


async def remove_curriculum_mapping(
    session: AsyncSession, mapping_id: uuid.UUID, actor_user_id: uuid.UUID
) -> None:
    mapping = await session.get(ActivityKnowledgePoint, mapping_id)
    if mapping is None:
        raise LookupError("Knowledge mapping not found")
    release = await _release_for_activity(session, mapping.activity_id)
    _require_draft(release)
    await session.delete(mapping)
    _audit(session, "course_updated", actor_user_id, release, node_type="knowledge_mapping")
    await session.commit()


def _issue(severity: str, code: str, message: str, path: str) -> CurriculumValidationIssue:
    return CurriculumValidationIssue(severity=severity, code=code, message=message, path=path)


async def validate_curriculum_release(
    session: AsyncSession, release: CurriculumRelease
) -> CurriculumValidationReport:
    course = await _course_for_release(session, release.id)
    units = list(
        (
            await session.scalars(
                select(CourseUnit)
                .where(
                    CourseUnit.course_id == course.id, CourseUnit.status != CourseStatus.ARCHIVED
                )
                .order_by(CourseUnit.order_index)
            )
        ).all()
    )
    issues: list[CurriculumValidationIssue] = []
    checks = {
        "structure_complete": True,
        "knowledge_points_valid": True,
        "subject_consistent": True,
        "domain_assets_available": True,
        "ordering_unique": True,
    }
    if not release.title.strip() or not course.title.strip():
        issues.append(_issue("error", "empty_title", "课程标题不能为空", "course.title"))
    if not units:
        issues.append(_issue("error", "missing_unit", "课程至少需要一个 Unit", "course.units"))
        checks["structure_complete"] = False
    unit_orders = [unit.order_index for unit in units]
    if len(unit_orders) != len(set(unit_orders)):
        issues.append(_issue("error", "duplicate_order", "Unit 顺序不能重复", "course.units"))
        checks["ordering_unique"] = False
    lesson_count = 0
    activity_count = 0
    point_count = 0
    for unit_index, unit in enumerate(units):
        unit_path = f"units[{unit_index}]"
        if not unit.title.strip():
            issues.append(_issue("error", "empty_title", "Unit 标题不能为空", unit_path))
        lessons = list(
            (
                await session.scalars(
                    select(CourseLesson)
                    .where(
                        CourseLesson.course_unit_id == unit.id,
                        CourseLesson.status != CourseStatus.ARCHIVED,
                    )
                    .order_by(CourseLesson.order_index)
                )
            ).all()
        )
        lesson_count += len(lessons)
        if not lessons:
            issues.append(_issue("error", "missing_lesson", "每个 Unit 都需要 Lesson", unit_path))
            checks["structure_complete"] = False
        lesson_orders = [lesson.order_index for lesson in lessons]
        if len(lesson_orders) != len(set(lesson_orders)):
            issues.append(
                _issue("error", "duplicate_order", "Lesson 顺序不能重复", f"{unit_path}.lessons")
            )
            checks["ordering_unique"] = False
        for lesson_index, lesson in enumerate(lessons):
            lesson_path = f"{unit_path}.lessons[{lesson_index}]"
            if not lesson.title.strip():
                issues.append(_issue("error", "empty_title", "Lesson 标题不能为空", lesson_path))
            activities = list(
                (
                    await session.scalars(
                        select(LearningActivity)
                        .where(
                            LearningActivity.lesson_id == lesson.id,
                            LearningActivity.status != CourseStatus.ARCHIVED,
                        )
                        .order_by(LearningActivity.order_index)
                    )
                ).all()
            )
            activity_count += len(activities)
            if not activities:
                issues.append(
                    _issue("error", "missing_activity", "每个 Lesson 都需要 Activity", lesson_path)
                )
                checks["structure_complete"] = False
            orders = [activity.order_index for activity in activities]
            if len(orders) != len(set(orders)):
                issues.append(
                    _issue(
                        "error",
                        "duplicate_order",
                        "Activity 顺序不能重复",
                        f"{lesson_path}.activities",
                    )
                )
                checks["ordering_unique"] = False
            for activity_index, activity in enumerate(activities):
                activity_path = f"{lesson_path}.activities[{activity_index}]"
                if not activity.title.strip():
                    issues.append(
                        _issue("error", "empty_title", "Activity 标题不能为空", activity_path)
                    )
                mappings = list(
                    (
                        await session.execute(
                            select(ActivityKnowledgePoint, KnowledgePoint)
                            .join(
                                KnowledgePoint,
                                KnowledgePoint.id == ActivityKnowledgePoint.knowledge_point_id,
                            )
                            .where(ActivityKnowledgePoint.activity_id == activity.id)
                            .order_by(ActivityKnowledgePoint.order_index)
                        )
                    ).all()
                )
                point_count += len(mappings)
                no_point_severity = (
                    "warning"
                    if activity.activity_type
                    in {"offline_instruction", "reading", "science_reference"}
                    else "error"
                )
                if not mappings:
                    issues.append(
                        _issue(
                            no_point_severity,
                            "missing_knowledge_point",
                            "Activity 尚未关联 KnowledgePoint",
                            activity_path,
                        )
                    )
                    if no_point_severity == "error":
                        checks["knowledge_points_valid"] = False
                for mapping_index, (_, point) in enumerate(mappings):
                    point_path = f"{activity_path}.knowledge_points[{mapping_index}]"
                    if point.status == KnowledgeStatus.ARCHIVED:
                        issues.append(
                            _issue(
                                "error",
                                "archived_knowledge_point",
                                f"KnowledgePoint {point.canonical_key} 已归档",
                                point_path,
                            )
                        )
                        checks["knowledge_points_valid"] = False
                    if point.subject != release.subject:
                        issues.append(
                            _issue(
                                "error",
                                "subject_mismatch",
                                f"{point.canonical_key} 与课程学科不一致",
                                point_path,
                            )
                        )
                        checks["subject_consistent"] = False
                    if point.type == "math_skill":
                        template = await session.scalar(
                            select(MathProblemTemplate.id).where(
                                MathProblemTemplate.knowledge_point_id == point.id,
                                MathProblemTemplate.status == "active",
                            )
                        )
                        if template is None:
                            issues.append(
                                _issue(
                                    "error",
                                    "math_template_unavailable",
                                    f"{point.canonical_key} 没有可运行数学模板",
                                    point_path,
                                )
                            )
                            checks["domain_assets_available"] = False
                    if point.type.startswith("pinyin_"):
                        pinyin = await session.get(PinyinItem, point.id)
                        if pinyin is None:
                            issues.append(
                                _issue(
                                    "error",
                                    "pinyin_strategy_unavailable",
                                    f"{point.canonical_key} 缺少拼音内容策略",
                                    point_path,
                                )
                            )
                            checks["domain_assets_available"] = False
                        elif pinyin.audio_key is None:
                            issues.append(
                                _issue(
                                    "warning",
                                    "pinyin_tts_fallback",
                                    f"{point.canonical_key} 将使用 TTS fallback",
                                    point_path,
                                )
                            )
                    if point.type.startswith("english_"):
                        english = await session.get(EnglishItem, point.id)
                        if english is None:
                            issues.append(
                                _issue(
                                    "error",
                                    "english_assets_unavailable",
                                    f"{point.canonical_key} 缺少英语内容",
                                    point_path,
                                )
                            )
                            checks["domain_assets_available"] = False
                        elif english.visual_type == "emoji_fallback" or english.audio_key is None:
                            issues.append(
                                _issue(
                                    "warning",
                                    "english_fallback",
                                    f"{point.canonical_key} 使用 audio/visual fallback",
                                    point_path,
                                )
                            )
                    if point.type == "chinese_character" and not point.canonical_key.startswith(
                        "zh-char:"
                    ):
                        issues.append(
                            _issue(
                                "error",
                                "invalid_chinese_canonical",
                                "汉字 Activity 必须引用 canonical Chinese knowledge",
                                point_path,
                            )
                        )
                        checks["knowledge_points_valid"] = False
    error_count = sum(issue.severity == "error" for issue in issues)
    warning_count = sum(issue.severity == "warning" for issue in issues)
    return CurriculumValidationReport(
        valid=error_count == 0,
        issues=issues,
        error_count=error_count,
        warning_count=warning_count,
        checks=checks,
        statistics={
            "units": len(units),
            "lessons": lesson_count,
            "activities": activity_count,
            "knowledge_points": point_count,
        },
    )


async def transition_curriculum_release(
    session: AsyncSession,
    release: CurriculumRelease,
    action: str,
    actor_user_id: uuid.UUID,
    *,
    confirm_warnings: bool = False,
) -> CurriculumRelease:
    now = datetime.now(UTC)
    course = await _course_for_release(session, release.id)
    if action == "submit":
        _require_draft(release)
        release.status = CurriculumReleaseStatus.IN_REVIEW
        _audit(session, "curriculum_submitted", actor_user_id, release)
    elif action == "return-to-draft":
        if release.status != CurriculumReleaseStatus.IN_REVIEW:
            raise ValueError("Only in-review releases can return to draft")
        release.status = CurriculumReleaseStatus.DRAFT
        release.reviewed_at = None
        release.reviewed_by_user_id = None
        _audit(session, "curriculum_reviewed", actor_user_id, release, outcome="returned")
    elif action == "review":
        if release.status != CurriculumReleaseStatus.IN_REVIEW:
            raise ValueError("Only in-review releases can be reviewed")
        release.reviewed_at = now
        release.reviewed_by_user_id = actor_user_id
        _audit(session, "curriculum_reviewed", actor_user_id, release, outcome="approved")
    elif action == "publish":
        if release.status != CurriculumReleaseStatus.IN_REVIEW or release.reviewed_at is None:
            raise ValueError("Release must be reviewed before publishing")
        report = await validate_curriculum_release(session, release)
        if report.error_count:
            raise ValueError("Curriculum validation has blocking errors")
        if report.warning_count and not confirm_warnings:
            raise ValueError("Curriculum validation warnings require confirmation")
        release.status = CurriculumReleaseStatus.PUBLISHED
        release.published_at = now
        release.published_by_user_id = actor_user_id
        release.validation_snapshot = report.model_dump(mode="json")
        course.status = CourseStatus.ENABLED
        for model, filter_expression in (
            (CourseUnit, CourseUnit.course_id == course.id),
            (
                CourseLesson,
                CourseLesson.course_unit_id.in_(
                    select(CourseUnit.id).where(CourseUnit.course_id == course.id)
                ),
            ),
            (
                LearningActivity,
                LearningActivity.course_unit_id.in_(
                    select(CourseUnit.id).where(CourseUnit.course_id == course.id)
                ),
            ),
        ):
            nodes = list((await session.scalars(select(model).where(filter_expression))).all())
            for node in nodes:
                if node.status == CourseStatus.DRAFT:
                    node.status = CourseStatus.ENABLED
        _audit(session, "curriculum_published", actor_user_id, release)
    elif action == "archive":
        if release.status != CurriculumReleaseStatus.PUBLISHED:
            raise ValueError("Only published releases can be archived")
        release.status = CurriculumReleaseStatus.ARCHIVED
        release.archived_at = now
        course.status = CourseStatus.ARCHIVED
        _audit(session, "curriculum_archived", actor_user_id, release)
    else:
        raise ValueError("Unsupported curriculum transition")
    await session.commit()
    return release


async def clone_curriculum_release(
    session: AsyncSession,
    source: CurriculumRelease,
    payload: CurriculumNewVersionRequest,
    actor_user_id: uuid.UUID,
) -> CurriculumRelease:
    if source.status not in {
        CurriculumReleaseStatus.PUBLISHED,
        CurriculumReleaseStatus.ARCHIVED,
    }:
        raise ValueError("Only published or archived releases can create a new version")
    new_payload = CurriculumReleaseCreate(
        curriculum_key=source.curriculum_key,
        release_version=payload.release_version,
        education_stage=source.education_stage,
        grade_level=source.grade_level,
        semester=source.semester,
        subject=source.subject,
        title=source.title,
        description=source.description,
        source_type=source.source_type,
        source_name=source.source_name,
        source_reference=source.source_reference,
        license=source.license,
        copyright_notice=source.copyright_notice,
        change_summary=payload.change_summary,
        metadata_json=dict(source.metadata_json),
    )
    target, target_course = await create_curriculum_release(
        session, new_payload, actor_user_id, commit=False
    )
    source_course = await _course_for_release(session, source.id)
    units = list(
        (
            await session.scalars(
                select(CourseUnit)
                .where(CourseUnit.course_id == source_course.id)
                .order_by(CourseUnit.order_index)
            )
        ).all()
    )
    for unit in units:
        target_unit = CourseUnit(
            course_id=target_course.id,
            title=unit.title,
            description=unit.description,
            order_index=unit.order_index,
            status=CourseStatus.DRAFT
            if unit.status != CourseStatus.ARCHIVED
            else CourseStatus.ARCHIVED,
        )
        session.add(target_unit)
        await session.flush()
        lessons = list(
            (
                await session.scalars(
                    select(CourseLesson)
                    .where(CourseLesson.course_unit_id == unit.id)
                    .order_by(CourseLesson.order_index)
                )
            ).all()
        )
        for lesson in lessons:
            target_lesson = CourseLesson(
                course_unit_id=target_unit.id,
                title=lesson.title,
                description=lesson.description,
                order_index=lesson.order_index,
                estimated_minutes=lesson.estimated_minutes,
                status=(
                    CourseStatus.DRAFT
                    if lesson.status != CourseStatus.ARCHIVED
                    else CourseStatus.ARCHIVED
                ),
                metadata_json=dict(lesson.metadata_json),
            )
            session.add(target_lesson)
            await session.flush()
            activities = list(
                (
                    await session.scalars(
                        select(LearningActivity)
                        .where(LearningActivity.lesson_id == lesson.id)
                        .order_by(LearningActivity.order_index)
                    )
                ).all()
            )
            for activity in activities:
                target_activity = LearningActivity(
                    course_unit_id=target_unit.id,
                    lesson_id=target_lesson.id,
                    activity_type=activity.activity_type,
                    title=activity.title,
                    instructions=activity.instructions,
                    order_index=activity.order_index,
                    status=(
                        CourseStatus.DRAFT
                        if activity.status != CourseStatus.ARCHIVED
                        else CourseStatus.ARCHIVED
                    ),
                    content_metadata=dict(activity.content_metadata),
                )
                session.add(target_activity)
                await session.flush()
                mappings = list(
                    (
                        await session.scalars(
                            select(ActivityKnowledgePoint)
                            .where(ActivityKnowledgePoint.activity_id == activity.id)
                            .order_by(ActivityKnowledgePoint.order_index)
                        )
                    ).all()
                )
                for mapping in mappings:
                    session.add(
                        ActivityKnowledgePoint(
                            activity_id=target_activity.id,
                            knowledge_point_id=mapping.knowledge_point_id,
                            role=mapping.role,
                            order_index=mapping.order_index,
                            reference_code=mapping.reference_code,
                            curriculum_metadata=dict(mapping.curriculum_metadata),
                        )
                    )
    _audit(
        session,
        "curriculum_version_created",
        actor_user_id,
        target,
        source_release_id=str(source.id),
    )
    await session.commit()
    return target


async def export_curriculum_release(
    session: AsyncSession, release: CurriculumRelease
) -> dict[str, Any]:
    course = await _course_for_release(session, release.id)
    document: dict[str, Any] = {
        "schema_version": "gl-curriculum-v1",
        "curriculum_version": release.release_version,
        "course": {
            "curriculum_key": release.curriculum_key,
            "release_version": release.release_version,
            "education_stage": release.education_stage,
            "grade_level": release.grade_level,
            "semester": release.semester,
            "subject": release.subject,
            "title": release.title,
            "description": release.description,
            "source_type": release.source_type,
            "source_name": release.source_name,
            "source_reference": release.source_reference,
            "license": release.license,
            "copyright_notice": release.copyright_notice,
            "change_summary": release.change_summary,
            "metadata_json": release.metadata_json,
        },
        "units": [],
    }
    units = list(
        (
            await session.scalars(
                select(CourseUnit)
                .where(CourseUnit.course_id == course.id)
                .order_by(CourseUnit.order_index)
            )
        ).all()
    )
    for unit in units:
        unit_json: dict[str, Any] = {
            "title": unit.title,
            "description": unit.description,
            "order_index": unit.order_index,
            "status": unit.status,
            "lessons": [],
        }
        lessons = list(
            (
                await session.scalars(
                    select(CourseLesson)
                    .where(CourseLesson.course_unit_id == unit.id)
                    .order_by(CourseLesson.order_index)
                )
            ).all()
        )
        for lesson in lessons:
            lesson_json: dict[str, Any] = {
                "title": lesson.title,
                "description": lesson.description,
                "order_index": lesson.order_index,
                "estimated_minutes": lesson.estimated_minutes,
                "status": lesson.status,
                "metadata_json": lesson.metadata_json,
                "activities": [],
            }
            activities = list(
                (
                    await session.scalars(
                        select(LearningActivity)
                        .where(LearningActivity.lesson_id == lesson.id)
                        .order_by(LearningActivity.order_index)
                    )
                ).all()
            )
            for activity in activities:
                mappings = list(
                    (
                        await session.execute(
                            select(ActivityKnowledgePoint, KnowledgePoint)
                            .join(
                                KnowledgePoint,
                                KnowledgePoint.id == ActivityKnowledgePoint.knowledge_point_id,
                            )
                            .where(ActivityKnowledgePoint.activity_id == activity.id)
                            .order_by(ActivityKnowledgePoint.order_index)
                        )
                    ).all()
                )
                lesson_json["activities"].append(
                    {
                        "title": activity.title,
                        "activity_type": activity.activity_type,
                        "instructions": activity.instructions,
                        "order_index": activity.order_index,
                        "status": activity.status,
                        "content_metadata": activity.content_metadata,
                        "knowledge_points": [
                            {
                                "canonical_key": point.canonical_key,
                                "role": mapping.role,
                                "order_index": mapping.order_index,
                                "reference_code": mapping.reference_code,
                                "metadata_json": mapping.curriculum_metadata,
                            }
                            for mapping, point in mappings
                        ],
                    }
                )
            unit_json["lessons"].append(lesson_json)
        document["units"].append(unit_json)
    return document


def _normalized_digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical_import_payload(
    release_payload: CurriculumReleaseCreate, document: CurriculumDocument
) -> dict[str, Any]:
    units: list[dict[str, Any]] = []
    for unit_index, unit in enumerate(document.units):
        lessons: list[dict[str, Any]] = []
        for lesson_index, lesson in enumerate(list(unit.get("lessons", []))):
            activities: list[dict[str, Any]] = []
            for activity_index, activity in enumerate(list(lesson.get("activities", []))):
                mappings = [
                    {
                        "canonical_key": mapping.get("canonical_key"),
                        "role": mapping.get("role", "primary"),
                        "order_index": mapping_index,
                        "reference_code": mapping.get("reference_code"),
                        "metadata_json": dict(mapping.get("metadata_json", {})),
                    }
                    for mapping_index, mapping in enumerate(
                        list(activity.get("knowledge_points", []))
                    )
                ]
                activities.append(
                    {
                        "title": activity.get("title", ""),
                        "activity_type": activity.get("activity_type", "knowledge_learning"),
                        "instructions": activity.get("instructions"),
                        "order_index": activity_index,
                        "status": "draft",
                        "content_metadata": dict(activity.get("content_metadata", {})),
                        "knowledge_points": mappings,
                    }
                )
            lessons.append(
                {
                    "title": lesson.get("title", ""),
                    "description": lesson.get("description"),
                    "order_index": lesson_index,
                    "estimated_minutes": lesson.get("estimated_minutes"),
                    "status": "draft",
                    "metadata_json": dict(lesson.get("metadata_json", {})),
                    "activities": activities,
                }
            )
        units.append(
            {
                "title": unit.get("title", ""),
                "description": unit.get("description"),
                "order_index": unit_index,
                "status": "draft",
                "lessons": lessons,
            }
        )
    return {
        "schema_version": "gl-curriculum-v1",
        "curriculum_version": release_payload.release_version,
        "course": release_payload.model_dump(mode="json"),
        "units": units,
    }


async def import_curriculum_document(
    session: AsyncSession,
    document: CurriculumDocument,
    actor_user_id: uuid.UUID,
    *,
    dry_run: bool,
) -> CurriculumImportReport:
    errors: list[str] = []
    warnings: list[str] = []
    course_data = dict(document.course)
    if document.curriculum_version != course_data.get("release_version"):
        errors.append("curriculum_version must match course.release_version")
    try:
        release_payload = CurriculumReleaseCreate.model_validate(course_data)
    except Exception as error:
        return CurriculumImportReport(
            dry_run=dry_run,
            will_create=[],
            will_update=[],
            created=[],
            updated=[],
            errors=[str(error)],
            warnings=[],
        )
    canonical_keys: set[str] = set()
    for unit in document.units:
        for lesson in list(unit.get("lessons", [])):
            for activity in list(lesson.get("activities", [])):
                for mapping in list(activity.get("knowledge_points", [])):
                    key = mapping.get("canonical_key")
                    if isinstance(key, str):
                        canonical_keys.add(key)
                    else:
                        errors.append("Every knowledge point mapping requires canonical_key")
    point_rows = list(
        (
            await session.scalars(
                select(KnowledgePoint).where(KnowledgePoint.canonical_key.in_(canonical_keys))
            )
        ).all()
    )
    points = {point.canonical_key: point for point in point_rows}
    unknown = canonical_keys - points.keys()
    if unknown:
        errors.append("Unknown KnowledgePoint: " + ", ".join(sorted(unknown)))
    mismatched = [key for key, point in points.items() if point.subject != release_payload.subject]
    if mismatched:
        errors.append("KnowledgePoint subject mismatch: " + ", ".join(sorted(mismatched)))
    existing = await session.scalar(
        select(CurriculumRelease).where(
            CurriculumRelease.curriculum_key == release_payload.curriculum_key,
            CurriculumRelease.release_version == release_payload.release_version,
        )
    )
    if existing is not None:
        current = await export_curriculum_release(session, existing)
        expected = _canonical_import_payload(release_payload, document)
        if _normalized_digest(current) == _normalized_digest(expected):
            return CurriculumImportReport(
                dry_run=dry_run,
                will_create=[],
                will_update=[],
                created=[],
                updated=[],
                errors=errors,
                warnings=warnings,
                release_id=existing.id,
                idempotent=True,
            )
        errors.append("Release already exists with different content; create a new version")
    if errors:
        return CurriculumImportReport(
            dry_run=dry_run,
            will_create=[],
            will_update=[],
            created=[],
            updated=[],
            errors=errors,
            warnings=warnings,
        )
    creates = [
        f"release:{release_payload.curriculum_key}@{release_payload.release_version}",
        f"units:{len(document.units)}",
        f"knowledge_mappings:{len(canonical_keys)}",
    ]
    if dry_run:
        return CurriculumImportReport(
            dry_run=True,
            will_create=creates,
            will_update=[],
            created=[],
            updated=[],
            errors=[],
            warnings=warnings,
        )
    release, course = await create_curriculum_release(
        session, release_payload, actor_user_id, commit=False
    )
    for unit_index, unit_data in enumerate(document.units):
        unit = CourseUnit(
            course_id=course.id,
            title=str(unit_data.get("title", "")).strip(),
            description=unit_data.get("description"),
            order_index=unit_index,
            status=CourseStatus.DRAFT,
        )
        session.add(unit)
        await session.flush()
        for lesson_index, lesson_data in enumerate(list(unit_data.get("lessons", []))):
            lesson = CourseLesson(
                course_unit_id=unit.id,
                title=str(lesson_data.get("title", "")).strip(),
                description=lesson_data.get("description"),
                order_index=lesson_index,
                estimated_minutes=lesson_data.get("estimated_minutes"),
                status=CourseStatus.DRAFT,
                metadata_json=dict(lesson_data.get("metadata_json", {})),
            )
            session.add(lesson)
            await session.flush()
            for activity_index, activity_data in enumerate(list(lesson_data.get("activities", []))):
                activity = LearningActivity(
                    course_unit_id=unit.id,
                    lesson_id=lesson.id,
                    title=str(activity_data.get("title", "")).strip(),
                    activity_type=str(activity_data.get("activity_type", "knowledge_learning")),
                    instructions=activity_data.get("instructions"),
                    order_index=activity_index,
                    status=CourseStatus.DRAFT,
                    content_metadata=dict(activity_data.get("content_metadata", {})),
                )
                session.add(activity)
                await session.flush()
                for mapping_index, mapping_data in enumerate(
                    list(activity_data.get("knowledge_points", []))
                ):
                    point = points[str(mapping_data["canonical_key"])]
                    session.add(
                        ActivityKnowledgePoint(
                            activity_id=activity.id,
                            knowledge_point_id=point.id,
                            role=str(mapping_data.get("role", "primary")),
                            order_index=mapping_index,
                            reference_code=mapping_data.get("reference_code"),
                            curriculum_metadata=dict(mapping_data.get("metadata_json", {})),
                        )
                    )
    await session.commit()
    return CurriculumImportReport(
        dry_run=False,
        will_create=[],
        will_update=[],
        created=creates,
        updated=[],
        errors=[],
        warnings=warnings,
        release_id=release.id,
    )
