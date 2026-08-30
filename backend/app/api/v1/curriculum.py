"""System-admin curriculum content center and release workflow endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import DbSession, SystemAdmin
from app.models import CourseLesson, CourseUnit, CurriculumRelease, LearningActivity
from app.schemas.curriculum import (
    CurriculumActivityCreate,
    CurriculumDocument,
    CurriculumImportReport,
    CurriculumLessonCreate,
    CurriculumMappingCreate,
    CurriculumMoveRequest,
    CurriculumNewVersionRequest,
    CurriculumNodeUpdate,
    CurriculumPreviewResponse,
    CurriculumReleaseCreate,
    CurriculumReleaseResponse,
    CurriculumReleaseUpdate,
    CurriculumTransitionRequest,
    CurriculumUnitCreate,
    CurriculumValidationReport,
)
from app.services.curriculum import (
    add_curriculum_activity,
    add_curriculum_lesson,
    add_curriculum_mapping,
    add_curriculum_unit,
    clone_curriculum_release,
    create_curriculum_release,
    curriculum_release_for_node,
    export_curriculum_release,
    import_curriculum_document,
    list_curriculum_releases,
    move_curriculum_node,
    release_response,
    remove_curriculum_mapping,
    transition_curriculum_release,
    update_curriculum_node,
    update_curriculum_release,
    validate_curriculum_release,
)

router = APIRouter(prefix="/admin/curriculum", tags=["curriculum-admin"])


async def _release_or_404(session: DbSession, release_id: uuid.UUID) -> CurriculumRelease:
    release = await session.get(CurriculumRelease, release_id)
    if release is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release not found")
    return release


def _unprocessable(error: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


@router.get("/releases", response_model=list[CurriculumReleaseResponse])
async def admin_list_curriculum_releases(
    _admin: SystemAdmin,
    session: DbSession,
    education_stage: Annotated[
        str | None, Query(pattern="^(foundation|primary|junior_middle)$")
    ] = None,
    grade_level: Annotated[int | None, Query(ge=1, le=9)] = None,
    semester: Annotated[str | None, Query(pattern="^(full_year|semester_1|semester_2)$")] = None,
    subject: Annotated[str | None, Query(pattern="^(chinese|math|english|science)$")] = None,
    release_status: Annotated[
        str | None, Query(alias="status", pattern="^(draft|in_review|published|archived)$")
    ] = None,
) -> list[CurriculumReleaseResponse]:
    releases = await list_curriculum_releases(
        session,
        education_stage=education_stage,
        grade_level=grade_level,
        semester=semester,
        subject=subject,
        status=release_status,
    )
    return [await release_response(session, release) for release in releases]


@router.post(
    "/releases",
    response_model=CurriculumReleaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_curriculum_release(
    payload: CurriculumReleaseCreate, admin: SystemAdmin, session: DbSession
) -> CurriculumReleaseResponse:
    try:
        release, _ = await create_curriculum_release(session, payload, admin.id)
    except ValueError as error:
        raise _unprocessable(error) from error
    return await release_response(session, release, include_course=True)


@router.post("/import", response_model=CurriculumImportReport)
async def admin_import_curriculum(
    payload: CurriculumDocument,
    admin: SystemAdmin,
    session: DbSession,
    dry_run: bool = Query(default=True),
) -> CurriculumImportReport:
    return await import_curriculum_document(session, payload, admin.id, dry_run=dry_run)


@router.get("/releases/{release_id}", response_model=CurriculumReleaseResponse)
async def admin_get_curriculum_release(
    release_id: uuid.UUID, _admin: SystemAdmin, session: DbSession
) -> CurriculumReleaseResponse:
    release = await _release_or_404(session, release_id)
    return await release_response(session, release, include_course=True)


@router.patch("/releases/{release_id}", response_model=CurriculumReleaseResponse)
async def admin_update_curriculum_release(
    release_id: uuid.UUID,
    payload: CurriculumReleaseUpdate,
    admin: SystemAdmin,
    session: DbSession,
) -> CurriculumReleaseResponse:
    release = await _release_or_404(session, release_id)
    try:
        release = await update_curriculum_release(session, release, payload, admin.id)
    except ValueError as error:
        raise _unprocessable(error) from error
    return await release_response(session, release, include_course=True)


@router.post("/releases/{release_id}/units", response_model=CurriculumReleaseResponse)
async def admin_add_curriculum_unit(
    release_id: uuid.UUID,
    payload: CurriculumUnitCreate,
    admin: SystemAdmin,
    session: DbSession,
) -> CurriculumReleaseResponse:
    release = await _release_or_404(session, release_id)
    try:
        await add_curriculum_unit(session, release, payload, admin.id)
    except ValueError as error:
        raise _unprocessable(error) from error
    return await release_response(session, release, include_course=True)


@router.post("/units/{unit_id}/lessons", response_model=CurriculumReleaseResponse)
async def admin_add_curriculum_lesson(
    unit_id: uuid.UUID,
    payload: CurriculumLessonCreate,
    admin: SystemAdmin,
    session: DbSession,
) -> CurriculumReleaseResponse:
    unit = await session.get(CourseUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    try:
        await add_curriculum_lesson(session, unit, payload, admin.id)
    except ValueError as error:
        raise _unprocessable(error) from error
    release = await curriculum_release_for_node(session, "unit", unit_id)
    return await release_response(session, release, include_course=True)


@router.post("/lessons/{lesson_id}/activities", response_model=CurriculumReleaseResponse)
async def admin_add_curriculum_activity(
    lesson_id: uuid.UUID,
    payload: CurriculumActivityCreate,
    admin: SystemAdmin,
    session: DbSession,
) -> CurriculumReleaseResponse:
    lesson = await session.get(CourseLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    try:
        await add_curriculum_activity(session, lesson, payload, admin.id)
    except ValueError as error:
        raise _unprocessable(error) from error
    release = await curriculum_release_for_node(session, "lesson", lesson_id)
    return await release_response(session, release, include_course=True)


@router.post("/activities/{activity_id}/knowledge-points", response_model=CurriculumReleaseResponse)
async def admin_add_curriculum_mapping(
    activity_id: uuid.UUID,
    payload: CurriculumMappingCreate,
    admin: SystemAdmin,
    session: DbSession,
) -> CurriculumReleaseResponse:
    activity = await session.get(LearningActivity, activity_id)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    try:
        await add_curriculum_mapping(session, activity, payload, admin.id)
    except ValueError as error:
        raise _unprocessable(error) from error
    release = await curriculum_release_for_node(session, "activity", activity_id)
    return await release_response(session, release, include_course=True)


@router.delete("/knowledge-mappings/{mapping_id}")
async def admin_remove_curriculum_mapping(
    mapping_id: uuid.UUID, admin: SystemAdmin, session: DbSession
) -> dict[str, bool]:
    try:
        await remove_curriculum_mapping(session, mapping_id, admin.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise _unprocessable(error) from error
    return {"removed": True}


@router.patch("/nodes/{node_type}/{node_id}", response_model=CurriculumReleaseResponse)
async def admin_update_curriculum_node(
    node_type: str,
    node_id: uuid.UUID,
    payload: CurriculumNodeUpdate,
    admin: SystemAdmin,
    session: DbSession,
) -> CurriculumReleaseResponse:
    try:
        await update_curriculum_node(session, node_type, node_id, payload, admin.id)
        release = await curriculum_release_for_node(session, node_type, node_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise _unprocessable(error) from error
    return await release_response(session, release, include_course=True)


@router.post("/nodes/{node_type}/{node_id}/move", response_model=CurriculumReleaseResponse)
async def admin_move_curriculum_node(
    node_type: str,
    node_id: uuid.UUID,
    payload: CurriculumMoveRequest,
    admin: SystemAdmin,
    session: DbSession,
) -> CurriculumReleaseResponse:
    try:
        await move_curriculum_node(session, node_type, node_id, payload.direction, admin.id)
        release = await curriculum_release_for_node(session, node_type, node_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise _unprocessable(error) from error
    return await release_response(session, release, include_course=True)


@router.get("/releases/{release_id}/validate", response_model=CurriculumValidationReport)
async def admin_validate_curriculum_release(
    release_id: uuid.UUID, _admin: SystemAdmin, session: DbSession
) -> CurriculumValidationReport:
    release = await _release_or_404(session, release_id)
    return await validate_curriculum_release(session, release)


@router.get("/releases/{release_id}/preview", response_model=CurriculumPreviewResponse)
async def admin_preview_curriculum_release(
    release_id: uuid.UUID, _admin: SystemAdmin, session: DbSession
) -> CurriculumPreviewResponse:
    release = await _release_or_404(session, release_id)
    return CurriculumPreviewResponse(
        release=await release_response(session, release, include_course=True)
    )


@router.post("/releases/{release_id}/transition/{action}", response_model=CurriculumReleaseResponse)
async def admin_transition_curriculum_release(
    release_id: uuid.UUID,
    action: str,
    payload: CurriculumTransitionRequest,
    admin: SystemAdmin,
    session: DbSession,
) -> CurriculumReleaseResponse:
    release = await _release_or_404(session, release_id)
    try:
        release = await transition_curriculum_release(
            session,
            release,
            action,
            admin.id,
            confirm_warnings=payload.confirm_warnings,
        )
    except ValueError as error:
        raise _unprocessable(error) from error
    return await release_response(session, release, include_course=True)


@router.post("/releases/{release_id}/new-version", response_model=CurriculumReleaseResponse)
async def admin_clone_curriculum_release(
    release_id: uuid.UUID,
    payload: CurriculumNewVersionRequest,
    admin: SystemAdmin,
    session: DbSession,
) -> CurriculumReleaseResponse:
    source = await _release_or_404(session, release_id)
    try:
        release = await clone_curriculum_release(session, source, payload, admin.id)
    except ValueError as error:
        raise _unprocessable(error) from error
    return await release_response(session, release, include_course=True)


@router.get("/releases/{release_id}/export")
async def admin_export_curriculum_release(
    release_id: uuid.UUID, _admin: SystemAdmin, session: DbSession
) -> dict[str, object]:
    release = await _release_or_404(session, release_id)
    return await export_curriculum_release(session, release)
