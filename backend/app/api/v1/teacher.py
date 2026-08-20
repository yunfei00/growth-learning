"""Parent-authorized teacher, classroom, assignment, and observation APIs."""

import uuid

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.teacher import (
    AssignmentAnalytics,
    ClassroomCreate,
    ClassroomResponse,
    ClassroomUpdate,
    ConnectionResolveResponse,
    ParentConnectRequest,
    ParentTeacherCollaboration,
    TeacherAssignmentCreate,
    TeacherAssignmentResponse,
    TeacherDashboard,
    TeacherObservationCreate,
    TeacherObservationResponse,
    TeacherProfileCreate,
    TeacherProfileResponse,
    TeacherProfileUpdate,
    TeacherRelationResponse,
    TeacherStudentSummary,
    TeacherTaskListItem,
    TeacherTaskProgressResponse,
    TeacherTaskSubmission,
)
from app.services.teacher_collaboration import (
    assignment_analytics,
    assignment_response,
    connect_teacher_or_classroom,
    create_assignment,
    create_classroom,
    create_observation,
    create_teacher_profile,
    leave_classroom,
    list_assignments,
    list_child_teacher_tasks,
    list_classrooms,
    list_teacher_students,
    parent_collaboration,
    publish_assignment,
    require_owned_assignment,
    require_teacher_profile,
    resolve_connection,
    revoke_teacher,
    rotate_teacher_code,
    start_or_resume_task,
    submit_task_progress,
    teacher_dashboard,
    teacher_student_summary,
    update_classroom,
    update_teacher_profile,
)

router = APIRouter(tags=["teacher collaboration"])


@router.post(
    "/teacher/profile",
    response_model=TeacherProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enable_teacher_mode(
    payload: TeacherProfileCreate, current_user: CurrentUser, session: DbSession
) -> TeacherProfileResponse:
    return await create_teacher_profile(session, current_user, payload)


@router.get("/teacher/profile", response_model=TeacherProfileResponse)
async def get_teacher_profile(
    current_user: CurrentUser, session: DbSession
) -> TeacherProfileResponse:
    profile = await require_teacher_profile(session, current_user, active=False)
    return TeacherProfileResponse.model_validate(profile, from_attributes=True)


@router.patch("/teacher/profile", response_model=TeacherProfileResponse)
async def patch_teacher_profile(
    payload: TeacherProfileUpdate, current_user: CurrentUser, session: DbSession
) -> TeacherProfileResponse:
    return await update_teacher_profile(session, current_user, payload)


@router.post("/teacher/profile/rotate-code", response_model=TeacherProfileResponse)
async def rotate_profile_code(
    current_user: CurrentUser, session: DbSession
) -> TeacherProfileResponse:
    return await rotate_teacher_code(session, current_user)


@router.get("/teacher/dashboard", response_model=TeacherDashboard)
async def get_teacher_dashboard(current_user: CurrentUser, session: DbSession) -> TeacherDashboard:
    return await teacher_dashboard(session, current_user)


@router.post(
    "/teacher/classrooms",
    response_model=ClassroomResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_classroom(
    payload: ClassroomCreate, current_user: CurrentUser, session: DbSession
) -> ClassroomResponse:
    return await create_classroom(session, current_user, payload.name, payload.description)


@router.get("/teacher/classrooms", response_model=list[ClassroomResponse])
async def get_classrooms(current_user: CurrentUser, session: DbSession) -> list[ClassroomResponse]:
    return await list_classrooms(session, current_user)


@router.patch("/teacher/classrooms/{classroom_id}", response_model=ClassroomResponse)
async def patch_classroom(
    classroom_id: uuid.UUID,
    payload: ClassroomUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> ClassroomResponse:
    return await update_classroom(
        session,
        current_user,
        classroom_id,
        name=payload.name,
        description=payload.description,
        classroom_status=payload.status,
    )


@router.get("/teacher/connections/resolve", response_model=ConnectionResolveResponse)
async def get_connection_summary(
    current_user: CurrentUser,
    session: DbSession,
    code: str = Query(min_length=12, max_length=64),
) -> ConnectionResolveResponse:
    del current_user
    return await resolve_connection(session, code)


@router.post(
    "/children/{child_id}/teacher-connections",
    response_model=TeacherRelationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_child_teacher(
    child_id: uuid.UUID,
    payload: ParentConnectRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> TeacherRelationResponse:
    return await connect_teacher_or_classroom(session, current_user, child_id, payload.code)


@router.post(
    "/children/{child_id}/teacher-connections/{relation_id}/revoke",
    response_model=TeacherRelationResponse,
)
async def revoke_child_teacher(
    child_id: uuid.UUID,
    relation_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> TeacherRelationResponse:
    return await revoke_teacher(session, current_user, child_id, relation_id)


@router.post(
    "/children/{child_id}/teacher-classrooms/{membership_id}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def leave_child_classroom(
    child_id: uuid.UUID,
    membership_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    await leave_classroom(session, current_user, child_id, membership_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/children/{child_id}/teacher-collaboration",
    response_model=ParentTeacherCollaboration,
)
async def get_parent_teacher_collaboration(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> ParentTeacherCollaboration:
    return await parent_collaboration(session, current_user, child_id)


@router.post(
    "/teacher/assignments",
    response_model=TeacherAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_assignment(
    payload: TeacherAssignmentCreate, current_user: CurrentUser, session: DbSession
) -> TeacherAssignmentResponse:
    return await create_assignment(session, current_user, payload)


@router.get("/teacher/assignments", response_model=list[TeacherAssignmentResponse])
async def get_assignments(
    current_user: CurrentUser, session: DbSession
) -> list[TeacherAssignmentResponse]:
    return await list_assignments(session, current_user)


@router.get("/teacher/assignments/{assignment_id}", response_model=TeacherAssignmentResponse)
async def get_assignment(
    assignment_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> TeacherAssignmentResponse:
    profile, assignment = await require_owned_assignment(session, current_user, assignment_id)
    return await assignment_response(session, assignment, profile)


@router.post(
    "/teacher/assignments/{assignment_id}/publish",
    response_model=TeacherAssignmentResponse,
)
async def publish_teacher_assignment(
    assignment_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> TeacherAssignmentResponse:
    return await publish_assignment(session, current_user, assignment_id)


@router.get("/teacher/assignments/{assignment_id}/analytics", response_model=AssignmentAnalytics)
async def get_assignment_analytics(
    assignment_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> AssignmentAnalytics:
    return await assignment_analytics(session, current_user, assignment_id)


@router.get("/teacher/students", response_model=list[TeacherStudentSummary])
async def get_teacher_students(
    current_user: CurrentUser, session: DbSession
) -> list[TeacherStudentSummary]:
    return await list_teacher_students(session, current_user)


@router.get("/teacher/students/{child_id}", response_model=TeacherStudentSummary)
async def get_teacher_student(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> TeacherStudentSummary:
    return await teacher_student_summary(session, current_user, child_id)


@router.post(
    "/teacher/students/{child_id}/observations",
    response_model=TeacherObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_teacher_observation(
    child_id: uuid.UUID,
    payload: TeacherObservationCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> TeacherObservationResponse:
    return await create_observation(session, current_user, child_id, payload)


@router.get("/children/{child_id}/teacher-tasks", response_model=list[TeacherTaskListItem])
async def get_child_teacher_tasks(
    child_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> list[TeacherTaskListItem]:
    return await list_child_teacher_tasks(session, current_user, child_id)


@router.post(
    "/children/{child_id}/teacher-tasks/{assignment_id}/start",
    response_model=TeacherTaskProgressResponse,
)
async def start_child_teacher_task(
    child_id: uuid.UUID,
    assignment_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> TeacherTaskProgressResponse:
    return await start_or_resume_task(session, current_user, child_id, assignment_id)


@router.post(
    "/children/{child_id}/teacher-tasks/{assignment_id}/progress",
    response_model=TeacherTaskProgressResponse,
)
async def submit_child_teacher_task(
    child_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: TeacherTaskSubmission,
    current_user: CurrentUser,
    session: DbSession,
) -> TeacherTaskProgressResponse:
    return await submit_task_progress(session, current_user, child_id, assignment_id, payload)
