"""Family invitations, member administration, relations, and evidence-backed activity."""

import uuid

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession
from app.models import (
    AdultChildRelation,
    Child,
    ExperimentSession,
    Family,
    FamilyInvitation,
    FamilyMember,
    GrowthEvent,
    LearningRecord,
    LearningSession,
    ReadingSession,
    ScienceExperiment,
    StoryVersion,
    User,
)
from app.schemas.family import (
    AdultChildRelationResponse,
    AdultChildRelationUpdate,
    FamilyActivityResponse,
    FamilyInvitationAcceptRequest,
    FamilyInvitationAcceptResponse,
    FamilyInvitationCreate,
    FamilyInvitationCreatedResponse,
    FamilyInvitationResponse,
    FamilyMemberResponse,
    FamilyMemberRoleUpdate,
    MemberUserResponse,
)
from app.services.authorization import require_family_admin, require_family_membership
from app.services.family_collaboration import (
    FamilyInvitationAcceptanceResult,
    FamilyInvitationUnavailableError,
    accept_email_bound_family_invitation,
    accept_family_invitation_code,
    create_family_invitation,
    effective_family_invitation_status,
    remove_family_member,
    revoke_family_invitation,
    set_adult_child_relation,
    update_family_member_role,
    utc_now,
)

router = APIRouter(tags=["family collaboration"])


def _invitation_response(
    invitation: FamilyInvitation,
    *,
    family_name: str,
    creator_name: str,
) -> FamilyInvitationResponse:
    return FamilyInvitationResponse(
        id=invitation.id,
        family_id=invitation.family_id,
        family_name=family_name,
        code_hint=invitation.code_hint,
        status=effective_family_invitation_status(invitation),
        role_to_grant=invitation.role_to_grant,
        email_constraint=invitation.email_constraint,
        created_by_user_id=invitation.created_by_user_id,
        created_by_display_name=creator_name,
        expires_at=invitation.expires_at,
        used_count=invitation.used_count,
        revoked_at=invitation.revoked_at,
        accepted_by_user_id=invitation.accepted_by_user_id,
        accepted_at=invitation.accepted_at,
        created_at=invitation.created_at,
        updated_at=invitation.updated_at,
    )


async def _member_response(session: DbSession, member: FamilyMember) -> FamilyMemberResponse:
    user = await session.get(User, member.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Family member user not found")
    relations = list(
        (
            await session.scalars(
                select(AdultChildRelation)
                .where(
                    AdultChildRelation.family_id == member.family_id,
                    AdultChildRelation.user_id == member.user_id,
                )
                .order_by(AdultChildRelation.created_at, AdultChildRelation.id)
            )
        ).all()
    )
    return FamilyMemberResponse(
        id=member.id,
        role=member.role,
        user=MemberUserResponse.model_validate(user),
        relations=[
            AdultChildRelationResponse.model_validate(item, from_attributes=True)
            for item in relations
        ],
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


def _acceptance_response(
    result: FamilyInvitationAcceptanceResult,
) -> FamilyInvitationAcceptResponse:
    return FamilyInvitationAcceptResponse(
        family_id=result.family.id,
        family_name=result.family.name,
        membership_id=result.membership.id,
        role=result.membership.role,
        already_member=result.already_member,
    )


def _raise_invitation_error(error: FamilyInvitationUnavailableError) -> None:
    statuses = {
        "wrong_email": status.HTTP_403_FORBIDDEN,
        "expired": status.HTTP_410_GONE,
        "revoked": status.HTTP_409_CONFLICT,
        "used": status.HTTP_409_CONFLICT,
        "invalid": status.HTTP_404_NOT_FOUND,
    }
    raise HTTPException(
        status_code=statuses.get(error.reason, status.HTTP_400_BAD_REQUEST),
        detail="家庭邀请不可用",
    ) from error


@router.post(
    "/families/{family_id}/invitations",
    response_model=FamilyInvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    family_id: uuid.UUID,
    payload: FamilyInvitationCreate,
    request: Request,
    current_user: CurrentUser,
    session: DbSession,
) -> FamilyInvitationCreatedResponse:
    await require_family_admin(session, current_user, family_id)
    family = await session.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    try:
        result = await create_family_invitation(
            session,
            request.app.state.settings,
            family=family,
            actor=current_user,
            role_to_grant=payload.role_to_grant,
            email_constraint=(str(payload.email_constraint) if payload.email_constraint else None),
            expires_at=payload.expires_at,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    public = _invitation_response(
        result.invitation,
        family_name=family.name,
        creator_name=current_user.display_name,
    )
    return FamilyInvitationCreatedResponse(
        **public.model_dump(), invitation_code=result.plaintext_code
    )


@router.get(
    "/families/{family_id}/invitations",
    response_model=list[FamilyInvitationResponse],
)
async def list_invitations(
    family_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> list[FamilyInvitationResponse]:
    await require_family_admin(session, current_user, family_id)
    rows = (
        await session.execute(
            select(FamilyInvitation, Family.name, User.display_name)
            .join(Family, Family.id == FamilyInvitation.family_id)
            .join(User, User.id == FamilyInvitation.created_by_user_id)
            .where(FamilyInvitation.family_id == family_id)
            .order_by(FamilyInvitation.created_at.desc(), FamilyInvitation.id)
        )
    ).all()
    return [
        _invitation_response(row[0], family_name=row[1], creator_name=row[2]) for row in rows
    ]


@router.post(
    "/families/{family_id}/invitations/{invitation_id}/revoke",
    response_model=FamilyInvitationResponse,
)
async def revoke_invitation(
    family_id: uuid.UUID,
    invitation_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> FamilyInvitationResponse:
    await require_family_admin(session, current_user, family_id)
    invitation = await revoke_family_invitation(
        session,
        family_id=family_id,
        invitation_id=invitation_id,
        actor=current_user,
    )
    if invitation is None:
        raise HTTPException(status_code=404, detail="家庭邀请不存在")
    family_name = await session.scalar(select(Family.name).where(Family.id == family_id))
    creator_name = await session.scalar(
        select(User.display_name).where(User.id == invitation.created_by_user_id)
    )
    return _invitation_response(
        invitation,
        family_name=family_name or "家庭",
        creator_name=creator_name or "家庭管理员",
    )


@router.get("/family-invitations/pending", response_model=list[FamilyInvitationResponse])
async def pending_invitations(
    current_user: CurrentUser, session: DbSession
) -> list[FamilyInvitationResponse]:
    rows = (
        await session.execute(
            select(FamilyInvitation, Family.name, User.display_name)
            .join(Family, Family.id == FamilyInvitation.family_id)
            .join(User, User.id == FamilyInvitation.created_by_user_id)
            .where(
                FamilyInvitation.email_constraint == current_user.email,
                FamilyInvitation.revoked_at.is_(None),
                FamilyInvitation.accepted_by_user_id.is_(None),
                FamilyInvitation.used_count < FamilyInvitation.max_uses,
                FamilyInvitation.expires_at > utc_now(),
            )
            .order_by(FamilyInvitation.created_at.desc())
        )
    ).all()
    return [
        _invitation_response(row[0], family_name=row[1], creator_name=row[2]) for row in rows
    ]


@router.post(
    "/family-invitations/accept",
    response_model=FamilyInvitationAcceptResponse,
)
async def accept_invitation_by_code(
    payload: FamilyInvitationAcceptRequest,
    request: Request,
    current_user: CurrentUser,
    session: DbSession,
) -> FamilyInvitationAcceptResponse:
    try:
        result = await accept_family_invitation_code(
            session,
            request.app.state.settings,
            invitation_code=payload.invitation_code,
            current_user=current_user,
        )
    except FamilyInvitationUnavailableError as error:
        _raise_invitation_error(error)
    return _acceptance_response(result)


@router.post(
    "/family-invitations/{invitation_id}/accept",
    response_model=FamilyInvitationAcceptResponse,
)
async def accept_email_invitation(
    invitation_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> FamilyInvitationAcceptResponse:
    try:
        result = await accept_email_bound_family_invitation(
            session, invitation_id=invitation_id, current_user=current_user
        )
    except FamilyInvitationUnavailableError as error:
        _raise_invitation_error(error)
    return _acceptance_response(result)


@router.patch(
    "/families/{family_id}/members/{member_id}",
    response_model=FamilyMemberResponse,
)
async def change_member_role(
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: FamilyMemberRoleUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> FamilyMemberResponse:
    await require_family_admin(session, current_user, family_id)
    try:
        member = await update_family_member_role(
            session,
            family_id=family_id,
            member_id=member_id,
            role=payload.role,
            actor=current_user,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if member is None:
        raise HTTPException(status_code=404, detail="家庭成员不存在")
    return await _member_response(session, member)


@router.delete(
    "/families/{family_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    await require_family_admin(session, current_user, family_id)
    try:
        removed = await remove_family_member(
            session,
            family_id=family_id,
            member_id=member_id,
            actor=current_user,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if not removed:
        raise HTTPException(status_code=404, detail="家庭成员不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/families/{family_id}/members/{member_id}/relations/{child_id}",
    response_model=AdultChildRelationResponse,
)
async def update_relation(
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    child_id: uuid.UUID,
    payload: AdultChildRelationUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> AdultChildRelationResponse:
    await require_family_admin(session, current_user, family_id)
    relation = await set_adult_child_relation(
        session,
        family_id=family_id,
        member_id=member_id,
        child_id=child_id,
        relation=payload.relation,
        actor=current_user,
    )
    if relation is None:
        raise HTTPException(status_code=404, detail="家庭成员或孩子不存在")
    return AdultChildRelationResponse.model_validate(relation, from_attributes=True)


@router.get(
    "/families/{family_id}/activity",
    response_model=list[FamilyActivityResponse],
)
async def family_activity(
    family_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[FamilyActivityResponse]:
    """Project recent household activity directly from canonical evidence."""
    await require_family_membership(session, current_user, family_id)
    items: list[FamilyActivityResponse] = []

    learning_rows = (
        await session.execute(
            select(
                LearningSession,
                Child.display_name,
                User.display_name,
                func.count(LearningRecord.id),
            )
            .join(Child, Child.id == LearningSession.child_id)
            .outerjoin(User, User.id == LearningSession.actor_user_id)
            .outerjoin(LearningRecord, LearningRecord.session_id == LearningSession.id)
            .where(Child.family_id == family_id, LearningSession.completed_at.is_not(None))
            .group_by(LearningSession.id, Child.display_name, User.display_name)
            .order_by(LearningSession.completed_at.desc())
            .limit(limit)
        )
    ).all()
    for learning, child_name, actor_name, record_count in learning_rows:
        items.append(
            FamilyActivityResponse(
                id=learning.id,
                kind="learning",
                child_id=learning.child_id,
                child_name=child_name,
                actor_user_id=learning.actor_user_id,
                actor_display_name=actor_name,
                title=f"完成识字学习（{record_count} 个学习记录）",
                occurred_at=learning.completed_at,
            )
        )

    reading_rows = (
        await session.execute(
            select(ReadingSession, Child.display_name, User.display_name, StoryVersion.title)
            .join(Child, Child.id == ReadingSession.child_id)
            .join(StoryVersion, StoryVersion.id == ReadingSession.story_version_id)
            .outerjoin(User, User.id == ReadingSession.evaluator_user_id)
            .where(Child.family_id == family_id, ReadingSession.completed_at.is_not(None))
            .order_by(ReadingSession.completed_at.desc())
            .limit(limit)
        )
    ).all()
    for reading, child_name, actor_name, story_title in reading_rows:
        items.append(
            FamilyActivityResponse(
                id=reading.id,
                kind="reading",
                child_id=reading.child_id,
                child_name=child_name,
                actor_user_id=reading.evaluator_user_id,
                actor_display_name=actor_name,
                title=f"读完《{story_title}》",
                occurred_at=reading.completed_at,
            )
        )

    science_rows = (
        await session.execute(
            select(
                ExperimentSession,
                Child.display_name,
                User.display_name,
                ScienceExperiment.title,
            )
            .join(Child, Child.id == ExperimentSession.child_id)
            .join(ScienceExperiment, ScienceExperiment.id == ExperimentSession.experiment_id)
            .outerjoin(User, User.id == ExperimentSession.accompanying_user_id)
            .where(Child.family_id == family_id, ExperimentSession.completed_at.is_not(None))
            .order_by(ExperimentSession.completed_at.desc())
            .limit(limit)
        )
    ).all()
    for science, child_name, actor_name, experiment_title in science_rows:
        items.append(
            FamilyActivityResponse(
                id=science.id,
                kind="science",
                child_id=science.child_id,
                child_name=child_name,
                actor_user_id=science.accompanying_user_id,
                actor_display_name=actor_name,
                title=f"完成科学实验“{experiment_title}”",
                occurred_at=science.completed_at,
            )
        )

    growth_rows = (
        await session.execute(
            select(GrowthEvent, Child.display_name, User.display_name)
            .join(Child, Child.id == GrowthEvent.child_id)
            .outerjoin(User, User.id == GrowthEvent.actor_user_id)
            .where(Child.family_id == family_id, GrowthEvent.source_type != "system")
            .order_by(GrowthEvent.occurred_at.desc())
            .limit(limit)
        )
    ).all()
    for event, child_name, actor_name in growth_rows:
        items.append(
            FamilyActivityResponse(
                id=event.id,
                kind="growth",
                child_id=event.child_id,
                child_name=child_name,
                actor_user_id=event.actor_user_id,
                actor_display_name=actor_name,
                title=event.title,
                occurred_at=event.occurred_at,
            )
        )

    return sorted(items, key=lambda item: item.occurred_at, reverse=True)[:limit]
