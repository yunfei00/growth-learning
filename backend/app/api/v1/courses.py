"""Reusable course, enrollment, catalog, and canonical activity endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession, SystemAdmin
from app.models import (
    ChildCourseEnrollment,
    Course,
    CourseSourceType,
    CourseSubject,
    EducationStage,
    EnrollmentStatus,
    GradeLevel,
    Semester,
    TeacherProfile,
)
from app.schemas.course import (
    CatalogImportResponse,
    CatalogReleaseResponse,
    CourseActivityCompletionResponse,
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    EnrollmentCreate,
    EnrollmentResponse,
    EnrollmentUpdate,
    PathCopyRequest,
    PathCopyResponse,
)
from app.services.authorization import get_authorized_child, require_family_admin
from app.services.character_catalog import import_expanded_catalog
from app.services.courses import (
    complete_character_activity,
    copy_course_path,
    course_response,
    create_course,
    current_catalog,
    enroll_child,
    enrollment_response,
    teacher_courses,
    visible_courses,
)

router = APIRouter(tags=["courses"])


@router.get("/courses", response_model=list[CourseResponse])
async def list_available_courses(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    subject: Annotated[CourseSubject | None, Query()] = None,
    grade_level: Annotated[GradeLevel | None, Query()] = None,
    semester: Annotated[Semester | None, Query()] = None,
    education_stage: Annotated[EducationStage | None, Query()] = None,
) -> list[CourseResponse]:
    child, _ = await get_authorized_child(session, current_user, child_id)
    courses = await visible_courses(
        session, child.id, child.family_id, subject, grade_level, semester, education_stage
    )
    return [await course_response(session, course, child.id) for course in courses]


@router.get("/courses/{course_id}", response_model=CourseResponse)
async def get_course_detail(
    course_id: uuid.UUID,
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> CourseResponse:
    child, _ = await get_authorized_child(session, current_user, child_id)
    courses = await visible_courses(session, child.id, child.family_id)
    course = next((item for item in courses if item.id == course_id), None)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return await course_response(session, course, child.id)


@router.post("/families/{family_id}/courses", response_model=CourseResponse)
async def create_family_course(
    family_id: uuid.UUID,
    payload: CourseCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> CourseResponse:
    await require_family_admin(session, current_user, family_id)
    if payload.source_type not in (
        CourseSourceType.FAMILY,
        CourseSourceType.TEXTBOOK_REFERENCE,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Family endpoint accepts family or textbook_reference courses",
        )
    try:
        course = await create_course(session, payload, current_user.id, family_id=family_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    return await course_response(session, course, None)


@router.patch("/families/{family_id}/courses/{course_id}", response_model=CourseResponse)
async def update_family_course(
    family_id: uuid.UUID,
    course_id: uuid.UUID,
    payload: CourseUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> CourseResponse:
    await require_family_admin(session, current_user, family_id)
    course = await session.scalar(
        select(Course).where(Course.id == course_id, Course.family_id == family_id)
    )
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(course, field, value)
    await session.commit()
    return await course_response(session, course, None)


@router.get("/teacher/courses", response_model=list[CourseResponse])
async def list_teacher_courses(
    current_user: CurrentUser,
    session: DbSession,
    subject: Annotated[CourseSubject | None, Query()] = None,
) -> list[CourseResponse]:
    try:
        courses = await teacher_courses(session, current_user.id, subject)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return [await course_response(session, course, None) for course in courses]


@router.post("/teacher/courses", response_model=CourseResponse)
async def create_teacher_course(
    payload: CourseCreate, current_user: CurrentUser, session: DbSession
) -> CourseResponse:
    profile = await session.scalar(
        select(TeacherProfile).where(TeacherProfile.user_id == current_user.id)
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teacher mode not enabled"
        )
    if payload.source_type != CourseSourceType.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Teacher endpoint accepts teacher courses",
        )
    try:
        course = await create_course(session, payload, current_user.id, teacher_id=profile.id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    return await course_response(session, course, None)


@router.patch("/teacher/courses/{course_id}", response_model=CourseResponse)
async def update_teacher_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> CourseResponse:
    profile = await session.scalar(
        select(TeacherProfile).where(TeacherProfile.user_id == current_user.id)
    )
    course = await session.scalar(
        select(Course).where(
            Course.id == course_id,
            Course.teacher_id == (profile.id if profile else None),
        )
    )
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(course, field, value)
    await session.commit()
    return await course_response(session, course, None)


@router.get("/children/{child_id}/course-enrollments", response_model=list[EnrollmentResponse])
async def list_child_enrollments(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> list[EnrollmentResponse]:
    await get_authorized_child(session, current_user, child_id)
    rows = list(
        (
            await session.scalars(
                select(ChildCourseEnrollment)
                .where(ChildCourseEnrollment.child_id == child_id)
                .order_by(ChildCourseEnrollment.path_order)
            )
        ).all()
    )
    return [await enrollment_response(session, row) for row in rows]


@router.post("/children/{child_id}/course-enrollments", response_model=EnrollmentResponse)
async def create_child_enrollment(
    child_id: uuid.UUID,
    payload: EnrollmentCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> EnrollmentResponse:
    child, _ = await get_authorized_child(session, current_user, child_id, admin_required=True)
    try:
        enrollment = await enroll_child(
            session,
            child.id,
            child.family_id,
            payload.course_id,
            payload.path_order,
            payload.status,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return await enrollment_response(session, enrollment)


@router.patch(
    "/children/{child_id}/course-enrollments/{enrollment_id}",
    response_model=EnrollmentResponse,
)
async def update_child_enrollment(
    child_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    payload: EnrollmentUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> EnrollmentResponse:
    await get_authorized_child(session, current_user, child_id, admin_required=True)
    enrollment = await session.scalar(
        select(ChildCourseEnrollment).where(
            ChildCourseEnrollment.id == enrollment_id,
            ChildCourseEnrollment.child_id == child_id,
        )
    )
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    now = datetime.now(UTC)
    values = payload.model_dump(exclude_none=True)
    for field, value in values.items():
        setattr(enrollment, field, value)
    if values.get("status") == EnrollmentStatus.ACTIVE and enrollment.started_at is None:
        enrollment.started_at = now
    if values.get("status") == EnrollmentStatus.COMPLETED:
        enrollment.completed_at = now
    await session.commit()
    return await enrollment_response(session, enrollment)


@router.post("/children/{source_child_id}/course-path/copy", response_model=PathCopyResponse)
async def copy_child_course_path(
    source_child_id: uuid.UUID,
    payload: PathCopyRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> PathCopyResponse:
    source, _ = await get_authorized_child(
        session, current_user, source_child_id, admin_required=True
    )
    target, _ = await get_authorized_child(
        session, current_user, payload.target_child_id, admin_required=True
    )
    if source.family_id != target.family_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")
    return await copy_course_path(session, source.id, target.id)


@router.post(
    "/children/{child_id}/course-activities/{activity_id}/complete",
    response_model=CourseActivityCompletionResponse,
)
async def complete_course_activity(
    child_id: uuid.UUID,
    activity_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> CourseActivityCompletionResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await complete_character_activity(session, child_id, activity_id, current_user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/admin/catalog", response_model=CatalogReleaseResponse)
async def get_admin_catalog(_admin: SystemAdmin, session: DbSession) -> CatalogReleaseResponse:
    result = await current_catalog(session)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog not imported")
    return result


@router.post("/admin/catalog/import", response_model=CatalogImportResponse)
async def import_admin_catalog(_admin: SystemAdmin, session: DbSession) -> CatalogImportResponse:
    result = await import_expanded_catalog(session)
    return CatalogImportResponse(**result.__dict__)


@router.get("/admin/courses", response_model=list[CourseResponse])
async def list_admin_courses(
    _admin: SystemAdmin,
    session: DbSession,
    subject: Annotated[CourseSubject | None, Query()] = None,
    grade_level: Annotated[GradeLevel | None, Query()] = None,
    semester: Annotated[Semester | None, Query()] = None,
) -> list[CourseResponse]:
    filters = [Course.source_type == CourseSourceType.SYSTEM]
    if subject is not None:
        filters.append(Course.subject == subject)
    if grade_level is not None:
        filters.append(Course.grade_level == grade_level)
    if semester is not None:
        filters.append(Course.semester == semester)
    courses = list(
        (
            await session.scalars(
                select(Course).where(*filters).order_by(Course.subject, Course.created_at)
            )
        ).all()
    )
    return [await course_response(session, course, None) for course in courses]


@router.post("/admin/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_course(
    payload: CourseCreate, admin: SystemAdmin, session: DbSession
) -> CourseResponse:
    if payload.source_type != CourseSourceType.SYSTEM:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Admin endpoint accepts system courses",
        )
    try:
        course = await create_course(session, payload, admin.id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    return await course_response(session, course, None)


@router.patch("/admin/courses/{course_id}", response_model=CourseResponse)
async def update_admin_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    _admin: SystemAdmin,
    session: DbSession,
) -> CourseResponse:
    course = await session.scalar(
        select(Course).where(
            Course.id == course_id,
            Course.source_type == CourseSourceType.SYSTEM,
        )
    )
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.curriculum_release_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Release-backed courses must use the curriculum workflow",
        )
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(course, field, value)
    await session.commit()
    return await course_response(session, course, None)
