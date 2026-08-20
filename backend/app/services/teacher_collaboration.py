"""Teacher collaboration service with live grants and canonical evidence reuse."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentItem,
    AssessmentOutcome,
    AssessmentSession,
    Child,
    ChildKnowledgeState,
    ChineseCharacter,
    Classroom,
    ClassroomMembership,
    ClassroomMembershipStatus,
    ClassroomStatus,
    FamilyMember,
    GrowthEvent,
    GrowthEventCategory,
    GrowthEventType,
    GrowthSourceType,
    KnowledgePoint,
    KnowledgeStatus,
    LearningActivityType,
    LearningRecord,
    LearningSession,
    ReadingSession,
    ReadingStatus,
    SessionStatus,
    TeacherAssignment,
    TeacherAssignmentKnowledgePoint,
    TeacherAssignmentProgress,
    TeacherAssignmentStatus,
    TeacherAssignmentTarget,
    TeacherAssignmentType,
    TeacherChildRelation,
    TeacherObservation,
    TeacherObservationKnowledgePoint,
    TeacherProfile,
    TeacherProfileStatus,
    TeacherProgressStatus,
    TeacherRelationStatus,
    User,
)
from app.schemas.teacher import (
    AssignmentAnalytics,
    AssignmentCharacter,
    AssignmentTargetSummary,
    ClassroomMembershipResponse,
    ClassroomResponse,
    ConnectionResolveResponse,
    ParentTeacherCollaboration,
    TeacherAssignmentCreate,
    TeacherAssignmentResponse,
    TeacherDashboard,
    TeacherObservationCreate,
    TeacherObservationResponse,
    TeacherProfileCreate,
    TeacherProfileResponse,
    TeacherProfileUpdate,
    TeacherPublicProfile,
    TeacherRelationResponse,
    TeacherStudentMastery,
    TeacherStudentSummary,
    TeacherTaskListItem,
    TeacherTaskProgressResponse,
    TeacherTaskSubmission,
)
from app.services.authorization import get_authorized_child
from app.services.mastery import recompute_child_knowledge_state
from app.services.review_planning import recompute_review_schedule

TEACHER_SCOPE_V1 = {
    "child_identity": "display_name_and_age_band",
    "mastery": "assigned_characters_only",
    "assignment_evidence": "own_assignments_only",
    "observations": "own_only",
}


def _public_profile(profile: TeacherProfile) -> TeacherPublicProfile:
    return TeacherPublicProfile(
        id=profile.id,
        display_name=profile.display_name,
        organization_name=profile.organization_name,
        short_bio=profile.short_bio,
    )


def _profile_response(profile: TeacherProfile) -> TeacherProfileResponse:
    return TeacherProfileResponse(
        id=profile.id,
        display_name=profile.display_name,
        organization_name=profile.organization_name,
        short_bio=profile.short_bio,
        teacher_code=profile.teacher_code,
        status=profile.status,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _age_band(birth_date: date) -> str:
    today = date.today()
    age = max(
        0,
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day)),
    )
    return f"{age}～{age + 1}岁"


def _task_status(progress: TeacherAssignmentProgress, due_at: datetime | None) -> str:
    if progress.status != TeacherProgressStatus.COMPLETED and due_at is not None:
        comparable_due = due_at if due_at.tzinfo else due_at.replace(tzinfo=UTC)
        if comparable_due < datetime.now(UTC):
            return "overdue"
    return progress.status


async def _opaque_code(session: AsyncSession, column, prefix: str) -> str:
    for _ in range(8):
        candidate = f"{prefix}_{secrets.token_urlsafe(18)}"
        if await session.scalar(select(column).where(column == candidate)) is None:
            return candidate
    raise RuntimeError("Unable to allocate a unique share code")


async def require_teacher_profile(
    session: AsyncSession, user: User, *, active: bool = True
) -> TeacherProfile:
    profile = await session.scalar(select(TeacherProfile).where(TeacherProfile.user_id == user.id))
    if profile is None or (active and profile.status != TeacherProfileStatus.ACTIVE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher mode required")
    return profile


async def require_active_teacher_child(
    session: AsyncSession, user: User, child_id: uuid.UUID
) -> tuple[TeacherProfile, TeacherChildRelation, Child]:
    profile = await require_teacher_profile(session, user)
    row = (
        await session.execute(
            select(TeacherChildRelation, Child)
            .join(Child, Child.id == TeacherChildRelation.child_id)
            .where(
                TeacherChildRelation.teacher_id == profile.id,
                TeacherChildRelation.child_id == child_id,
                TeacherChildRelation.status == TeacherRelationStatus.ACTIVE,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    relation, child = row
    return profile, relation, child


async def create_teacher_profile(
    session: AsyncSession, user: User, payload: TeacherProfileCreate
) -> TeacherProfileResponse:
    existing = await session.scalar(select(TeacherProfile).where(TeacherProfile.user_id == user.id))
    if existing is not None:
        return _profile_response(existing)
    profile = TeacherProfile(
        user_id=user.id,
        display_name=payload.display_name.strip(),
        organization_name=payload.organization_name.strip() if payload.organization_name else None,
        short_bio=payload.short_bio.strip() if payload.short_bio else None,
        teacher_code=await _opaque_code(session, TeacherProfile.teacher_code, "t"),
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return _profile_response(profile)


async def update_teacher_profile(
    session: AsyncSession, user: User, payload: TeacherProfileUpdate
) -> TeacherProfileResponse:
    profile = await require_teacher_profile(session, user, active=False)
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        setattr(profile, field, value.strip() if isinstance(value, str) else value)
    await session.commit()
    await session.refresh(profile)
    return _profile_response(profile)


async def rotate_teacher_code(session: AsyncSession, user: User) -> TeacherProfileResponse:
    profile = await require_teacher_profile(session, user)
    profile.teacher_code = await _opaque_code(session, TeacherProfile.teacher_code, "t")
    await session.commit()
    await session.refresh(profile)
    return _profile_response(profile)


async def classroom_response(session: AsyncSession, classroom: Classroom) -> ClassroomResponse:
    student_count = int(
        await session.scalar(
            select(func.count())
            .select_from(ClassroomMembership)
            .join(
                TeacherChildRelation,
                TeacherChildRelation.id == ClassroomMembership.relation_id,
            )
            .where(
                ClassroomMembership.classroom_id == classroom.id,
                ClassroomMembership.status == ClassroomMembershipStatus.ACTIVE,
                TeacherChildRelation.status == TeacherRelationStatus.ACTIVE,
            )
        )
        or 0
    )
    return ClassroomResponse(
        id=classroom.id,
        name=classroom.name,
        description=classroom.description,
        class_code=classroom.class_code,
        status=classroom.status,
        student_count=student_count,
        created_at=classroom.created_at,
        updated_at=classroom.updated_at,
    )


async def create_classroom(
    session: AsyncSession, user: User, name: str, description: str | None
) -> ClassroomResponse:
    profile = await require_teacher_profile(session, user)
    classroom = Classroom(
        teacher_id=profile.id,
        name=name.strip(),
        description=description.strip() if description else None,
        class_code=await _opaque_code(session, Classroom.class_code, "c"),
    )
    session.add(classroom)
    await session.commit()
    await session.refresh(classroom)
    return await classroom_response(session, classroom)


async def require_owned_classroom(
    session: AsyncSession, user: User, classroom_id: uuid.UUID, *, active: bool = False
) -> tuple[TeacherProfile, Classroom]:
    profile = await require_teacher_profile(session, user)
    classroom = await session.scalar(
        select(Classroom).where(
            Classroom.id == classroom_id,
            Classroom.teacher_id == profile.id,
        )
    )
    if classroom is None or (active and classroom.status != ClassroomStatus.ACTIVE):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classroom not found")
    return profile, classroom


async def list_classrooms(session: AsyncSession, user: User) -> list[ClassroomResponse]:
    profile = await require_teacher_profile(session, user)
    rows = list(
        await session.scalars(
            select(Classroom)
            .where(Classroom.teacher_id == profile.id)
            .order_by(Classroom.created_at.desc())
        )
    )
    return [await classroom_response(session, row) for row in rows]


async def update_classroom(
    session: AsyncSession,
    user: User,
    classroom_id: uuid.UUID,
    *,
    name: str | None,
    description: str | None,
    classroom_status: str | None,
) -> ClassroomResponse:
    _, classroom = await require_owned_classroom(session, user, classroom_id)
    if name is not None:
        classroom.name = name.strip()
    if description is not None:
        classroom.description = description.strip() or None
    if classroom_status is not None:
        classroom.status = classroom_status
    await session.commit()
    await session.refresh(classroom)
    return await classroom_response(session, classroom)


async def resolve_connection(session: AsyncSession, code: str) -> ConnectionResolveResponse:
    profile = await session.scalar(
        select(TeacherProfile).where(
            TeacherProfile.teacher_code == code,
            TeacherProfile.status == TeacherProfileStatus.ACTIVE,
        )
    )
    if profile is not None:
        return ConnectionResolveResponse(kind="teacher", teacher=_public_profile(profile))
    row = (
        await session.execute(
            select(Classroom, TeacherProfile)
            .join(TeacherProfile, TeacherProfile.id == Classroom.teacher_id)
            .where(
                Classroom.class_code == code,
                Classroom.status == ClassroomStatus.ACTIVE,
                TeacherProfile.status == TeacherProfileStatus.ACTIVE,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Connection code not found"
        )
    classroom, profile = row
    return ConnectionResolveResponse(
        kind="classroom",
        teacher=_public_profile(profile),
        classroom=await classroom_response(session, classroom),
    )


async def _activate_relation(
    session: AsyncSession,
    *,
    profile: TeacherProfile,
    child: Child,
    actor_user_id: uuid.UUID,
) -> TeacherChildRelation:
    relation = await session.scalar(
        select(TeacherChildRelation).where(
            TeacherChildRelation.teacher_id == profile.id,
            TeacherChildRelation.child_id == child.id,
        )
    )
    now = datetime.now(UTC)
    if relation is None:
        relation = TeacherChildRelation(
            teacher_id=profile.id,
            child_id=child.id,
            family_id=child.family_id,
            authorized_by_user_id=actor_user_id,
            authorized_at=now,
            permission_scope=TEACHER_SCOPE_V1,
        )
        session.add(relation)
        await session.flush()
    else:
        relation.status = TeacherRelationStatus.ACTIVE
        relation.authorized_by_user_id = actor_user_id
        relation.authorized_at = now
        relation.revoked_by_user_id = None
        relation.revoked_at = None
        relation.permission_scope = TEACHER_SCOPE_V1
        relation.permission_version = "teacher-scope-v1"
    return relation


async def connect_teacher_or_classroom(
    session: AsyncSession, user: User, child_id: uuid.UUID, code: str
) -> TeacherRelationResponse:
    child, _ = await get_authorized_child(session, user, child_id, admin_required=True)
    resolved = await resolve_connection(session, code)
    profile = await session.get(TeacherProfile, resolved.teacher.id)
    assert profile is not None
    relation = await _activate_relation(
        session, profile=profile, child=child, actor_user_id=user.id
    )
    if resolved.kind == "classroom":
        assert resolved.classroom is not None
        membership = await session.scalar(
            select(ClassroomMembership).where(
                ClassroomMembership.classroom_id == resolved.classroom.id,
                ClassroomMembership.child_id == child.id,
            )
        )
        now = datetime.now(UTC)
        if membership is None:
            session.add(
                ClassroomMembership(
                    classroom_id=resolved.classroom.id,
                    relation_id=relation.id,
                    child_id=child.id,
                    joined_by_user_id=user.id,
                    joined_at=now,
                )
            )
        else:
            membership.relation_id = relation.id
            membership.status = ClassroomMembershipStatus.ACTIVE
            membership.joined_by_user_id = user.id
            membership.joined_at = now
            membership.left_at = None
    await session.commit()
    await session.refresh(relation)
    return TeacherRelationResponse(
        id=relation.id,
        child_id=child.id,
        teacher=_public_profile(profile),
        status=relation.status,
        authorized_at=relation.authorized_at,
        revoked_at=relation.revoked_at,
        permission_version=relation.permission_version,
    )


async def revoke_teacher(
    session: AsyncSession,
    user: User,
    child_id: uuid.UUID,
    relation_id: uuid.UUID,
) -> TeacherRelationResponse:
    child, _ = await get_authorized_child(session, user, child_id, admin_required=True)
    row = (
        await session.execute(
            select(TeacherChildRelation, TeacherProfile)
            .join(TeacherProfile, TeacherProfile.id == TeacherChildRelation.teacher_id)
            .where(
                TeacherChildRelation.id == relation_id,
                TeacherChildRelation.child_id == child.id,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teacher relation not found"
        )
    relation, profile = row
    relation.status = TeacherRelationStatus.REVOKED
    relation.revoked_by_user_id = user.id
    relation.revoked_at = datetime.now(UTC)
    await session.commit()
    return TeacherRelationResponse(
        id=relation.id,
        child_id=child.id,
        teacher=_public_profile(profile),
        status=relation.status,
        authorized_at=relation.authorized_at,
        revoked_at=relation.revoked_at,
        permission_version=relation.permission_version,
    )


async def leave_classroom(
    session: AsyncSession, user: User, child_id: uuid.UUID, membership_id: uuid.UUID
) -> None:
    await get_authorized_child(session, user, child_id, admin_required=True)
    membership = await session.scalar(
        select(ClassroomMembership).where(
            ClassroomMembership.id == membership_id,
            ClassroomMembership.child_id == child_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Class membership not found"
        )
    membership.status = ClassroomMembershipStatus.LEFT
    membership.left_at = datetime.now(UTC)
    await session.commit()


async def _enabled_points(
    session: AsyncSession, point_ids: list[uuid.UUID]
) -> list[tuple[KnowledgePoint, ChineseCharacter]]:
    if not point_ids:
        return []
    rows = (
        await session.execute(
            select(KnowledgePoint, ChineseCharacter)
            .join(ChineseCharacter, ChineseCharacter.knowledge_point_id == KnowledgePoint.id)
            .where(
                KnowledgePoint.id.in_(point_ids),
                KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                ChineseCharacter.is_enabled.is_(True),
            )
        )
    ).all()
    by_id = {point.id: (point, character) for point, character in rows}
    if set(by_id) != set(point_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more enabled characters were not found",
        )
    return [by_id[point_id] for point_id in point_ids]


async def create_assignment(
    session: AsyncSession, user: User, payload: TeacherAssignmentCreate
) -> TeacherAssignmentResponse:
    profile = await require_teacher_profile(session, user)
    classroom: Classroom | None = None
    if payload.classroom_id:
        _, classroom = await require_owned_classroom(
            session, user, payload.classroom_id, active=True
        )

    target_ids = list(payload.target_child_ids)
    if classroom is not None and not target_ids:
        target_ids = list(
            await session.scalars(
                select(ClassroomMembership.child_id)
                .join(
                    TeacherChildRelation,
                    TeacherChildRelation.id == ClassroomMembership.relation_id,
                )
                .where(
                    ClassroomMembership.classroom_id == classroom.id,
                    ClassroomMembership.status == ClassroomMembershipStatus.ACTIVE,
                    TeacherChildRelation.teacher_id == profile.id,
                    TeacherChildRelation.status == TeacherRelationStatus.ACTIVE,
                )
            )
        )
    if not target_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No authorized children selected",
        )

    relation_rows = (
        (
            await session.execute(
                select(TeacherChildRelation)
                .where(
                    TeacherChildRelation.teacher_id == profile.id,
                    TeacherChildRelation.child_id.in_(target_ids),
                    TeacherChildRelation.status == TeacherRelationStatus.ACTIVE,
                )
                .order_by(TeacherChildRelation.child_id)
            )
        )
        .scalars()
        .all()
    )
    relations = {relation.child_id: relation for relation in relation_rows}
    if set(relations) != set(target_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Assignments may target only actively authorized children",
        )
    if classroom is not None:
        enrolled = set(
            await session.scalars(
                select(ClassroomMembership.child_id).where(
                    ClassroomMembership.classroom_id == classroom.id,
                    ClassroomMembership.child_id.in_(target_ids),
                    ClassroomMembership.status == ClassroomMembershipStatus.ACTIVE,
                )
            )
        )
        if enrolled != set(target_ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Class assignment targets must be parent-enrolled members",
            )

    await _enabled_points(session, payload.knowledge_point_ids)
    assignment = TeacherAssignment(
        teacher_id=profile.id,
        classroom_id=classroom.id if classroom else None,
        title=payload.title.strip(),
        instructions=payload.instructions.strip(),
        assignment_type=payload.assignment_type,
        due_at=payload.due_at,
    )
    session.add(assignment)
    await session.flush()
    for position, point_id in enumerate(payload.knowledge_point_ids, start=1):
        session.add(
            TeacherAssignmentKnowledgePoint(
                assignment_id=assignment.id,
                knowledge_point_id=point_id,
                position=position,
            )
        )
    for child_id in target_ids:
        session.add(
            TeacherAssignmentTarget(
                assignment_id=assignment.id,
                relation_id=relations[child_id].id,
                child_id=child_id,
            )
        )
        session.add(TeacherAssignmentProgress(assignment_id=assignment.id, child_id=child_id))
    await session.commit()
    await session.refresh(assignment)
    return await assignment_response(session, assignment, profile)


async def _assignment_characters(
    session: AsyncSession, assignment_id: uuid.UUID
) -> list[AssignmentCharacter]:
    rows = (
        await session.execute(
            select(TeacherAssignmentKnowledgePoint, ChineseCharacter)
            .join(
                ChineseCharacter,
                ChineseCharacter.knowledge_point_id
                == TeacherAssignmentKnowledgePoint.knowledge_point_id,
            )
            .where(TeacherAssignmentKnowledgePoint.assignment_id == assignment_id)
            .order_by(TeacherAssignmentKnowledgePoint.position)
        )
    ).all()
    return [
        AssignmentCharacter(
            knowledge_point_id=item.knowledge_point_id,
            character=character.character,
            pinyin=character.pinyin,
            position=item.position,
        )
        for item, character in rows
    ]


async def assignment_response(
    session: AsyncSession,
    assignment: TeacherAssignment,
    profile: TeacherProfile | None = None,
) -> TeacherAssignmentResponse:
    if profile is None:
        profile = await session.get(TeacherProfile, assignment.teacher_id)
        assert profile is not None
    classroom = (
        await session.get(Classroom, assignment.classroom_id) if assignment.classroom_id else None
    )
    characters = await _assignment_characters(session, assignment.id)
    rows = (
        await session.execute(
            select(
                TeacherAssignmentTarget,
                TeacherAssignmentProgress,
                Child,
                TeacherChildRelation,
            )
            .join(
                TeacherAssignmentProgress,
                and_(
                    TeacherAssignmentProgress.assignment_id
                    == TeacherAssignmentTarget.assignment_id,
                    TeacherAssignmentProgress.child_id == TeacherAssignmentTarget.child_id,
                ),
            )
            .join(Child, Child.id == TeacherAssignmentTarget.child_id)
            .join(
                TeacherChildRelation,
                TeacherChildRelation.id == TeacherAssignmentTarget.relation_id,
            )
            .where(TeacherAssignmentTarget.assignment_id == assignment.id)
            .order_by(Child.display_name)
        )
    ).all()
    targets = [
        AssignmentTargetSummary(
            child_id=child.id,
            child_name=(
                child.nickname or child.display_name
                if relation.status == TeacherRelationStatus.ACTIVE
                else "已撤销学生"
            ),
            progress_status=_task_status(progress, assignment.due_at),
            completed_item_count=progress.completed_item_count,
            total_item_count=len(characters),
        )
        for _, progress, child, relation in rows
    ]
    return TeacherAssignmentResponse(
        id=assignment.id,
        teacher=_public_profile(profile),
        classroom_id=assignment.classroom_id,
        classroom_name=classroom.name if classroom else None,
        title=assignment.title,
        instructions=assignment.instructions,
        assignment_type=assignment.assignment_type,
        due_at=assignment.due_at,
        status=assignment.status,
        published_at=assignment.published_at,
        characters=characters,
        targets=targets,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


async def list_assignments(session: AsyncSession, user: User) -> list[TeacherAssignmentResponse]:
    profile = await require_teacher_profile(session, user)
    assignments = list(
        await session.scalars(
            select(TeacherAssignment)
            .where(TeacherAssignment.teacher_id == profile.id)
            .order_by(TeacherAssignment.created_at.desc())
        )
    )
    return [await assignment_response(session, item, profile) for item in assignments]


async def require_owned_assignment(
    session: AsyncSession, user: User, assignment_id: uuid.UUID
) -> tuple[TeacherProfile, TeacherAssignment]:
    profile = await require_teacher_profile(session, user)
    assignment = await session.scalar(
        select(TeacherAssignment).where(
            TeacherAssignment.id == assignment_id,
            TeacherAssignment.teacher_id == profile.id,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return profile, assignment


async def publish_assignment(
    session: AsyncSession, user: User, assignment_id: uuid.UUID
) -> TeacherAssignmentResponse:
    profile, assignment = await require_owned_assignment(session, user, assignment_id)
    if assignment.status != TeacherAssignmentStatus.DRAFT:
        return await assignment_response(session, assignment, profile)
    target_count = int(
        await session.scalar(
            select(func.count())
            .select_from(TeacherAssignmentTarget)
            .join(
                TeacherChildRelation,
                TeacherChildRelation.id == TeacherAssignmentTarget.relation_id,
            )
            .where(
                TeacherAssignmentTarget.assignment_id == assignment.id,
                TeacherChildRelation.status == TeacherRelationStatus.ACTIVE,
            )
        )
        or 0
    )
    total_count = int(
        await session.scalar(
            select(func.count())
            .select_from(TeacherAssignmentTarget)
            .where(TeacherAssignmentTarget.assignment_id == assignment.id)
        )
        or 0
    )
    if target_count == 0 or target_count != total_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="All assignment targets require active parent authorization",
        )
    assignment.status = TeacherAssignmentStatus.PUBLISHED
    assignment.published_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(assignment)
    return await assignment_response(session, assignment, profile)


async def _task_item(
    session: AsyncSession,
    assignment: TeacherAssignment,
    progress: TeacherAssignmentProgress,
    profile: TeacherProfile,
) -> TeacherTaskListItem:
    classroom = (
        await session.get(Classroom, assignment.classroom_id) if assignment.classroom_id else None
    )
    characters = await _assignment_characters(session, assignment.id)
    return TeacherTaskListItem(
        assignment_id=assignment.id,
        teacher=_public_profile(profile),
        classroom_name=classroom.name if classroom else None,
        title=assignment.title,
        instructions=assignment.instructions,
        assignment_type=assignment.assignment_type,
        due_at=assignment.due_at,
        progress_status=_task_status(progress, assignment.due_at),
        completed_item_count=progress.completed_item_count,
        total_item_count=len(characters),
        characters=characters,
    )


async def list_child_teacher_tasks(
    session: AsyncSession, user: User, child_id: uuid.UUID
) -> list[TeacherTaskListItem]:
    await get_authorized_child(session, user, child_id)
    rows = (
        await session.execute(
            select(TeacherAssignment, TeacherAssignmentProgress, TeacherProfile)
            .join(
                TeacherAssignmentProgress,
                TeacherAssignmentProgress.assignment_id == TeacherAssignment.id,
            )
            .join(TeacherProfile, TeacherProfile.id == TeacherAssignment.teacher_id)
            .where(
                TeacherAssignmentProgress.child_id == child_id,
                TeacherAssignment.status.in_(
                    [TeacherAssignmentStatus.PUBLISHED, TeacherAssignmentStatus.CLOSED]
                ),
            )
            .order_by(TeacherAssignment.due_at, TeacherAssignment.created_at.desc())
        )
    ).all()
    return [
        await _task_item(session, assignment, progress, profile)
        for assignment, progress, profile in rows
    ]


async def _authorize_task_actor(
    session: AsyncSession,
    user: User,
    child_id: uuid.UUID,
    assignment_id: uuid.UUID,
) -> tuple[TeacherAssignment, TeacherAssignmentProgress, TeacherProfile, TeacherChildRelation]:
    row = (
        await session.execute(
            select(
                TeacherAssignment,
                TeacherAssignmentProgress,
                TeacherProfile,
                TeacherChildRelation,
                Child,
            )
            .join(
                TeacherAssignmentTarget,
                TeacherAssignmentTarget.assignment_id == TeacherAssignment.id,
            )
            .join(
                TeacherAssignmentProgress,
                and_(
                    TeacherAssignmentProgress.assignment_id == TeacherAssignment.id,
                    TeacherAssignmentProgress.child_id == TeacherAssignmentTarget.child_id,
                ),
            )
            .join(
                TeacherChildRelation,
                TeacherChildRelation.id == TeacherAssignmentTarget.relation_id,
            )
            .join(TeacherProfile, TeacherProfile.id == TeacherAssignment.teacher_id)
            .join(Child, Child.id == TeacherAssignmentTarget.child_id)
            .where(
                TeacherAssignment.id == assignment_id,
                TeacherAssignmentTarget.child_id == child_id,
                TeacherChildRelation.status == TeacherRelationStatus.ACTIVE,
                TeacherProfile.status == TeacherProfileStatus.ACTIVE,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher task not found")
    assignment, progress, profile, relation, child = row
    membership = await session.scalar(
        select(FamilyMember.id).where(
            FamilyMember.family_id == child.family_id,
            FamilyMember.user_id == user.id,
        )
    )
    actor_teacher = await session.scalar(
        select(TeacherProfile.id).where(
            TeacherProfile.user_id == user.id,
            TeacherProfile.id == relation.teacher_id,
            TeacherProfile.status == TeacherProfileStatus.ACTIVE,
        )
    )
    if membership is None and actor_teacher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher task not found")
    return assignment, progress, profile, relation


async def task_progress_response(
    session: AsyncSession,
    assignment: TeacherAssignment,
    progress: TeacherAssignmentProgress,
    profile: TeacherProfile,
) -> TeacherTaskProgressResponse:
    base = await _task_item(session, assignment, progress, profile)
    learning_ids: list[uuid.UUID] = []
    if progress.learning_session_id:
        learning_ids = list(
            await session.scalars(
                select(LearningRecord.knowledge_point_id).where(
                    LearningRecord.session_id == progress.learning_session_id
                )
            )
        )
    outcomes: dict[str, str] = {}
    if progress.assessment_session_id:
        rows = (
            await session.execute(
                select(AssessmentItem.knowledge_point_id, AssessmentItem.outcome).where(
                    AssessmentItem.session_id == progress.assessment_session_id
                )
            )
        ).all()
        outcomes = {str(point_id): outcome for point_id, outcome in rows}
    return TeacherTaskProgressResponse(
        **base.model_dump(),
        learning_session_id=progress.learning_session_id,
        assessment_session_id=progress.assessment_session_id,
        reading_session_id=progress.reading_session_id,
        started_at=progress.started_at,
        completed_at=progress.completed_at,
        completed_learning_point_ids=learning_ids,
        assessment_outcomes=outcomes,
    )


async def start_or_resume_task(
    session: AsyncSession, user: User, child_id: uuid.UUID, assignment_id: uuid.UUID
) -> TeacherTaskProgressResponse:
    assignment, progress, profile, _ = await _authorize_task_actor(
        session, user, child_id, assignment_id
    )
    if assignment.status != TeacherAssignmentStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assignment is not active")
    if progress.status == TeacherProgressStatus.PENDING:
        now = datetime.now(UTC)
        progress.status = TeacherProgressStatus.IN_PROGRESS
        progress.started_at = now
        if assignment.assignment_type in {
            TeacherAssignmentType.CHARACTER_LEARNING,
            TeacherAssignmentType.CHARACTER_REVIEW,
        }:
            evidence_session = LearningSession(
                child_id=child_id,
                actor_user_id=user.id,
                status=SessionStatus.IN_PROGRESS,
                source="teacher_assignment",
            )
            session.add(evidence_session)
            await session.flush()
            progress.learning_session_id = evidence_session.id
        elif assignment.assignment_type == TeacherAssignmentType.RECOGNITION_CHECK:
            evidence_session = AssessmentSession(
                child_id=child_id,
                evaluator_user_id=user.id,
                status=SessionStatus.IN_PROGRESS,
                source="teacher_assignment",
            )
            session.add(evidence_session)
            await session.flush()
            progress.assessment_session_id = evidence_session.id
        await session.commit()
        await session.refresh(progress)
    return await task_progress_response(session, assignment, progress, profile)


async def _assignment_point_ids(session: AsyncSession, assignment_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        await session.scalars(
            select(TeacherAssignmentKnowledgePoint.knowledge_point_id).where(
                TeacherAssignmentKnowledgePoint.assignment_id == assignment_id
            )
        )
    )


async def submit_task_progress(
    session: AsyncSession,
    user: User,
    child_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: TeacherTaskSubmission,
) -> TeacherTaskProgressResponse:
    assignment, progress, profile, _ = await _authorize_task_actor(
        session, user, child_id, assignment_id
    )
    if progress.status == TeacherProgressStatus.COMPLETED:
        return await task_progress_response(session, assignment, progress, profile)
    if progress.status == TeacherProgressStatus.PENDING:
        await start_or_resume_task(session, user, child_id, assignment_id)
        await session.refresh(progress)

    allowed_ids = await _assignment_point_ids(session, assignment.id)
    touched: set[uuid.UUID] = set()
    if assignment.assignment_type in {
        TeacherAssignmentType.CHARACTER_LEARNING,
        TeacherAssignmentType.CHARACTER_REVIEW,
    }:
        submitted = set(payload.learning_point_ids)
        if not submitted.issubset(allowed_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Submitted character is not in this assignment",
            )
        assert progress.learning_session_id is not None
        existing = set(
            await session.scalars(
                select(LearningRecord.knowledge_point_id).where(
                    LearningRecord.session_id == progress.learning_session_id
                )
            )
        )
        activity = (
            LearningActivityType.INTRODUCED
            if assignment.assignment_type == TeacherAssignmentType.CHARACTER_LEARNING
            else LearningActivityType.RELEARNED
        )
        for point_id in submitted - existing:
            session.add(
                LearningRecord(
                    session_id=progress.learning_session_id,
                    child_id=child_id,
                    knowledge_point_id=point_id,
                    actor_user_id=user.id,
                    activity_type=activity,
                    source="teacher_assignment",
                    learned_at=datetime.now(UTC),
                )
            )
        touched = submitted
        await session.flush()
        progress.completed_item_count = len(existing | submitted)
    elif assignment.assignment_type == TeacherAssignmentType.RECOGNITION_CHECK:
        submitted = {item.knowledge_point_id for item in payload.assessment_items}
        if not submitted.issubset(allowed_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Submitted character is not in this assignment",
            )
        assert progress.assessment_session_id is not None
        existing_rows = list(
            await session.scalars(
                select(AssessmentItem).where(
                    AssessmentItem.session_id == progress.assessment_session_id
                )
            )
        )
        existing = {item.knowledge_point_id: item for item in existing_rows}
        for item in payload.assessment_items:
            previous = existing.get(item.knowledge_point_id)
            if previous is not None:
                if previous.outcome != item.outcome:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Assessment evidence already exists with a different outcome",
                    )
                continue
            session.add(
                AssessmentItem(
                    session_id=progress.assessment_session_id,
                    child_id=child_id,
                    knowledge_point_id=item.knowledge_point_id,
                    evaluator_user_id=user.id,
                    outcome=item.outcome,
                    response_time_ms=item.response_time_ms,
                    hint_used=item.hint_used,
                    assessed_at=datetime.now(UTC),
                )
            )
        touched = submitted
        await session.flush()
        progress.completed_item_count = len(set(existing) | submitted)
    elif assignment.assignment_type == TeacherAssignmentType.READING:
        reading_session_id = payload.reading_session_id
        if reading_session_id is None and payload.complete:
            reading_session_id = await session.scalar(
                select(ReadingSession.id)
                .where(
                    ReadingSession.child_id == child_id,
                    ReadingSession.status == ReadingStatus.COMPLETED,
                    ReadingSession.completed_at >= assignment.published_at,
                )
                .order_by(ReadingSession.completed_at.desc())
                .limit(1)
            )
        if reading_session_id:
            reading = await session.scalar(
                select(ReadingSession).where(
                    ReadingSession.id == reading_session_id,
                    ReadingSession.child_id == child_id,
                    ReadingSession.status == ReadingStatus.COMPLETED,
                )
            )
            if reading is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A completed reading session for this child is required",
                )
            progress.reading_session_id = reading.id
            progress.completed_item_count = 1

    for point_id in touched:
        await recompute_child_knowledge_state(session, child_id, point_id, ensure_state=True)
        await recompute_review_schedule(session, child_id, point_id)

    if payload.complete:
        if assignment.assignment_type in {
            TeacherAssignmentType.CHARACTER_LEARNING,
            TeacherAssignmentType.CHARACTER_REVIEW,
            TeacherAssignmentType.RECOGNITION_CHECK,
        } and progress.completed_item_count != len(allowed_ids):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Complete every assignment character before finishing",
            )
        if (
            assignment.assignment_type == TeacherAssignmentType.READING
            and not progress.reading_session_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Complete a real reading session before finishing",
            )
        now = datetime.now(UTC)
        progress.status = TeacherProgressStatus.COMPLETED
        progress.completed_at = now
        if progress.learning_session_id:
            evidence = await session.get(LearningSession, progress.learning_session_id)
            assert evidence is not None
            evidence.status = SessionStatus.COMPLETED
            evidence.completed_at = now
        if progress.assessment_session_id:
            evidence = await session.get(AssessmentSession, progress.assessment_session_id)
            assert evidence is not None
            evidence.status = SessionStatus.COMPLETED
            evidence.completed_at = now
        event_key = f"teacher-assignment:{assignment.id}:{child_id}:completed"
        if (
            await session.scalar(
                select(GrowthEvent.id).where(
                    GrowthEvent.child_id == child_id,
                    GrowthEvent.idempotency_key == event_key,
                )
            )
            is None
        ):
            is_check = assignment.assignment_type == TeacherAssignmentType.RECOGNITION_CHECK
            session.add(
                GrowthEvent(
                    child_id=child_id,
                    event_type=(
                        GrowthEventType.ASSESSMENT_MILESTONE
                        if is_check
                        else GrowthEventType.LEARNING_MILESTONE
                    ),
                    category=(
                        GrowthEventCategory.ASSESSMENT if is_check else GrowthEventCategory.LEARNING
                    ),
                    occurred_at=now,
                    title="完成老师任务",
                    body=assignment.title,
                    source_type=GrowthSourceType.TEACHER,
                    actor_user_id=user.id,
                    source_entity_type="teacher_assignment",
                    source_entity_id=assignment.id,
                    idempotency_key=event_key,
                    evidence_snapshot={
                        "assignment_id": str(assignment.id),
                        "teacher_id": str(profile.id),
                        "assignment_type": assignment.assignment_type,
                    },
                    policy_version="teacher-growth-v1",
                )
            )
    await session.commit()
    await session.refresh(progress)
    return await task_progress_response(session, assignment, progress, profile)


async def create_observation(
    session: AsyncSession,
    user: User,
    child_id: uuid.UUID,
    payload: TeacherObservationCreate,
) -> TeacherObservationResponse:
    profile, relation, _ = await require_active_teacher_child(session, user, child_id)
    if payload.classroom_id:
        await require_owned_classroom(session, user, payload.classroom_id)
    if payload.assignment_id:
        _, assignment = await require_owned_assignment(session, user, payload.assignment_id)
        targeted = await session.scalar(
            select(TeacherAssignmentTarget.id).where(
                TeacherAssignmentTarget.assignment_id == assignment.id,
                TeacherAssignmentTarget.child_id == child_id,
            )
        )
        if targeted is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found"
            )
    await _enabled_points(session, payload.knowledge_point_ids)
    observation = TeacherObservation(
        teacher_id=profile.id,
        relation_id=relation.id,
        child_id=child_id,
        classroom_id=payload.classroom_id,
        assignment_id=payload.assignment_id,
        category=payload.category,
        original_text=payload.original_text,
        occurred_at=payload.occurred_at,
    )
    session.add(observation)
    await session.flush()
    for point_id in payload.knowledge_point_ids:
        session.add(
            TeacherObservationKnowledgePoint(
                observation_id=observation.id, knowledge_point_id=point_id
            )
        )
    session.add(
        GrowthEvent(
            child_id=child_id,
            event_type=GrowthEventType.FAMILY_OBSERVATION,
            category=GrowthEventCategory.LEARNING,
            occurred_at=payload.occurred_at,
            title=f"{profile.display_name}老师记录",
            body=payload.original_text,
            source_type=GrowthSourceType.TEACHER,
            actor_user_id=user.id,
            source_entity_type="teacher_observation",
            source_entity_id=observation.id,
            idempotency_key=f"teacher-observation:{observation.id}",
            evidence_snapshot={
                "observation_id": str(observation.id),
                "teacher_id": str(profile.id),
                "category": payload.category,
            },
            policy_version="teacher-growth-v1",
        )
    )
    await session.commit()
    await session.refresh(observation)
    return await observation_response(session, observation, profile)


async def observation_response(
    session: AsyncSession,
    observation: TeacherObservation,
    profile: TeacherProfile | None = None,
) -> TeacherObservationResponse:
    if profile is None:
        profile = await session.get(TeacherProfile, observation.teacher_id)
        assert profile is not None
    point_ids = list(
        await session.scalars(
            select(TeacherObservationKnowledgePoint.knowledge_point_id).where(
                TeacherObservationKnowledgePoint.observation_id == observation.id
            )
        )
    )
    return TeacherObservationResponse(
        id=observation.id,
        teacher=_public_profile(profile),
        child_id=observation.child_id,
        category=observation.category,
        original_text=observation.original_text,
        occurred_at=observation.occurred_at,
        classroom_id=observation.classroom_id,
        assignment_id=observation.assignment_id,
        knowledge_point_ids=point_ids,
        created_at=observation.created_at,
    )


async def teacher_student_summary(
    session: AsyncSession, user: User, child_id: uuid.UUID
) -> TeacherStudentSummary:
    profile, _, child = await require_active_teacher_child(session, user, child_id)
    task_rows = (
        await session.execute(
            select(TeacherAssignment, TeacherAssignmentProgress)
            .join(
                TeacherAssignmentProgress,
                TeacherAssignmentProgress.assignment_id == TeacherAssignment.id,
            )
            .where(
                TeacherAssignment.teacher_id == profile.id,
                TeacherAssignmentProgress.child_id == child_id,
                TeacherAssignment.status.in_(
                    [TeacherAssignmentStatus.PUBLISHED, TeacherAssignmentStatus.CLOSED]
                ),
            )
            .order_by(TeacherAssignment.created_at.desc())
        )
    ).all()
    assignments = [
        await _task_item(session, assignment, progress, profile)
        for assignment, progress in task_rows
    ]

    relevant_ids = set(
        await session.scalars(
            select(TeacherAssignmentKnowledgePoint.knowledge_point_id)
            .join(
                TeacherAssignment,
                TeacherAssignment.id == TeacherAssignmentKnowledgePoint.assignment_id,
            )
            .join(
                TeacherAssignmentTarget,
                TeacherAssignmentTarget.assignment_id == TeacherAssignment.id,
            )
            .where(
                TeacherAssignment.teacher_id == profile.id,
                TeacherAssignmentTarget.child_id == child_id,
            )
            .distinct()
        )
    )
    mastery: list[TeacherStudentMastery] = []
    if relevant_ids:
        rows = (
            await session.execute(
                select(ChineseCharacter, ChildKnowledgeState)
                .outerjoin(
                    ChildKnowledgeState,
                    and_(
                        ChildKnowledgeState.knowledge_point_id
                        == ChineseCharacter.knowledge_point_id,
                        ChildKnowledgeState.child_id == child_id,
                    ),
                )
                .where(ChineseCharacter.knowledge_point_id.in_(relevant_ids))
                .order_by(ChineseCharacter.character)
            )
        ).all()
        mastery = [
            TeacherStudentMastery(
                knowledge_point_id=character.knowledge_point_id,
                character=character.character,
                pinyin=character.pinyin,
                mastery_level=state.mastery_level if state else "unlearned",
                mastery_score=state.mastery_score if state else 0,
                is_priority=state.is_priority if state else False,
            )
            for character, state in rows
        ]
    observation_rows = list(
        await session.scalars(
            select(TeacherObservation)
            .where(
                TeacherObservation.teacher_id == profile.id,
                TeacherObservation.child_id == child_id,
            )
            .order_by(TeacherObservation.occurred_at.desc())
        )
    )
    observations = [
        await observation_response(session, observation, profile)
        for observation in observation_rows
    ]
    return TeacherStudentSummary(
        child_id=child.id,
        display_name=child.display_name,
        nickname=child.nickname,
        age_band=_age_band(child.birth_date),
        assignments=assignments,
        relevant_mastery=mastery,
        observations=observations,
    )


async def list_teacher_students(session: AsyncSession, user: User) -> list[TeacherStudentSummary]:
    profile = await require_teacher_profile(session, user)
    child_ids = list(
        await session.scalars(
            select(TeacherChildRelation.child_id)
            .where(
                TeacherChildRelation.teacher_id == profile.id,
                TeacherChildRelation.status == TeacherRelationStatus.ACTIVE,
            )
            .order_by(TeacherChildRelation.created_at)
        )
    )
    return [await teacher_student_summary(session, user, child_id) for child_id in child_ids]


async def assignment_analytics(
    session: AsyncSession, user: User, assignment_id: uuid.UUID
) -> AssignmentAnalytics:
    _, assignment = await require_owned_assignment(session, user, assignment_id)
    progress_rows = list(
        await session.scalars(
            select(TeacherAssignmentProgress).where(
                TeacherAssignmentProgress.assignment_id == assignment.id
            )
        )
    )
    statuses = [_task_status(progress, assignment.due_at) for progress in progress_rows]
    outcome_counts = {outcome.value: 0 for outcome in AssessmentOutcome}
    character_outcomes: dict[str, dict[str, int]] = {}
    if assignment.assignment_type == TeacherAssignmentType.RECOGNITION_CHECK:
        rows = (
            await session.execute(
                select(ChineseCharacter.character, AssessmentItem.outcome)
                .join(
                    TeacherAssignmentProgress,
                    TeacherAssignmentProgress.assessment_session_id == AssessmentItem.session_id,
                )
                .join(
                    ChineseCharacter,
                    ChineseCharacter.knowledge_point_id == AssessmentItem.knowledge_point_id,
                )
                .where(TeacherAssignmentProgress.assignment_id == assignment.id)
            )
        ).all()
        for character, outcome in rows:
            outcome_counts[outcome] += 1
            distribution = character_outcomes.setdefault(
                character, {value.value: 0 for value in AssessmentOutcome}
            )
            distribution[outcome] += 1
    common_errors = sorted(
        character_outcomes,
        key=lambda character: (
            character_outcomes[character][AssessmentOutcome.INCORRECT]
            + character_outcomes[character][AssessmentOutcome.UNCERTAIN],
            character,
        ),
        reverse=True,
    )
    common_errors = [
        character
        for character in common_errors
        if character_outcomes[character][AssessmentOutcome.INCORRECT]
        + character_outcomes[character][AssessmentOutcome.UNCERTAIN]
        > 0
    ][:10]
    return AssignmentAnalytics(
        assignment_id=assignment.id,
        total=len(progress_rows),
        pending=statuses.count("pending"),
        in_progress=statuses.count("in_progress"),
        completed=statuses.count("completed"),
        overdue=statuses.count("overdue"),
        outcome_counts=outcome_counts,
        character_outcomes=character_outcomes,
        common_errors=common_errors,
    )


async def parent_collaboration(
    session: AsyncSession, user: User, child_id: uuid.UUID
) -> ParentTeacherCollaboration:
    child, _ = await get_authorized_child(session, user, child_id)
    relation_rows = (
        await session.execute(
            select(TeacherChildRelation, TeacherProfile)
            .join(TeacherProfile, TeacherProfile.id == TeacherChildRelation.teacher_id)
            .where(
                TeacherChildRelation.child_id == child.id,
                TeacherChildRelation.family_id == child.family_id,
            )
            .order_by(TeacherChildRelation.authorized_at.desc())
        )
    ).all()
    relations = [
        TeacherRelationResponse(
            id=relation.id,
            child_id=child.id,
            teacher=_public_profile(profile),
            status=relation.status,
            authorized_at=relation.authorized_at,
            revoked_at=relation.revoked_at,
            permission_version=relation.permission_version,
        )
        for relation, profile in relation_rows
    ]
    class_rows = (
        await session.execute(
            select(ClassroomMembership, Classroom, TeacherProfile)
            .join(Classroom, Classroom.id == ClassroomMembership.classroom_id)
            .join(TeacherProfile, TeacherProfile.id == Classroom.teacher_id)
            .where(ClassroomMembership.child_id == child.id)
            .order_by(ClassroomMembership.joined_at.desc())
        )
    ).all()
    classrooms = [
        ClassroomMembershipResponse(
            id=membership.id,
            classroom_id=classroom.id,
            classroom_name=classroom.name,
            teacher=_public_profile(profile),
            status=membership.status,
            joined_at=membership.joined_at,
            left_at=membership.left_at,
        )
        for membership, classroom, profile in class_rows
    ]
    assignments = await list_child_teacher_tasks(session, user, child.id)
    observation_rows = (
        await session.execute(
            select(TeacherObservation, TeacherProfile)
            .join(TeacherProfile, TeacherProfile.id == TeacherObservation.teacher_id)
            .where(TeacherObservation.child_id == child.id)
            .order_by(TeacherObservation.occurred_at.desc())
        )
    ).all()
    observations = [
        await observation_response(session, observation, profile)
        for observation, profile in observation_rows
    ]
    return ParentTeacherCollaboration(
        relations=relations,
        classrooms=classrooms,
        assignments=assignments,
        observations=observations,
    )


async def teacher_dashboard(session: AsyncSession, user: User) -> TeacherDashboard:
    profile = await require_teacher_profile(session, user)
    classrooms = await list_classrooms(session, user)
    students = await list_teacher_students(session, user)
    assignments = await list_assignments(session, user)
    pending_review = sum(
        1
        for assignment in assignments
        for target in assignment.targets
        if target.progress_status == "completed"
    )
    recent_completed = sum(
        1
        for assignment in assignments
        for target in assignment.targets
        if target.progress_status == "completed"
    )
    return TeacherDashboard(
        profile=_profile_response(profile),
        classrooms=classrooms,
        students=students,
        assignments=assignments,
        pending_review_count=pending_review,
        recent_completed_count=recent_completed,
    )
