"""System-admin account lifecycle and platform invitation APIs."""

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.api.dependencies import DbSession, SystemAdmin, require_system_admin
from app.models import FamilyMember, PlatformInvitation, User
from app.schemas.platform_admin import (
    AdminUserPage,
    AdminUserResponse,
    AdminUserStatusUpdate,
    InvitationCreatedResponse,
    InvitationCreateRequest,
    InvitationPage,
    InvitationResponse,
)
from app.services.platform_access import (
    create_platform_invitation,
    effective_invitation_status,
    list_admin_users,
    revoke_platform_invitation,
    set_user_account_status,
)

router = APIRouter(
    prefix="/admin",
    tags=["platform account administration"],
    dependencies=[Depends(require_system_admin)],
)


def _user_response(user: User, family_count: int) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        account_status=user.account_status,
        system_role=user.system_role,
        registration_source=user.registration_source,
        registered_via_invitation_id=user.registered_via_invitation_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
        family_count=family_count,
    )


def _invitation_response(invitation: PlatformInvitation, creator_name: str) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        purpose=invitation.purpose,
        status=effective_invitation_status(invitation),
        code_hint=invitation.code_hint,
        created_by_user_id=invitation.created_by_user_id,
        created_by_display_name=creator_name,
        created_at=invitation.created_at,
        updated_at=invitation.updated_at,
        expires_at=invitation.expires_at,
        max_uses=invitation.max_uses,
        used_count=invitation.used_count,
        email_constraint=invitation.email_constraint,
        revoked_at=invitation.revoked_at,
        last_used_at=invitation.last_used_at,
    )


@router.get("/users", response_model=AdminUserPage)
async def admin_list_users(
    session: DbSession,
    search: str | None = Query(default=None, max_length=120),
    account_status: str | None = Query(default=None, pattern="^(active|suspended|disabled)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> AdminUserPage:
    result = await list_admin_users(
        session,
        search=search,
        account_status=account_status,
        page=page,
        page_size=page_size,
    )
    return AdminUserPage(
        items=[_user_response(item.user, item.family_count) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )


@router.patch("/users/{user_id}/status", response_model=AdminUserResponse)
async def admin_update_user_status(
    user_id: uuid.UUID,
    payload: AdminUserStatusUpdate,
    current_admin: SystemAdmin,
    session: DbSession,
) -> AdminUserResponse:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_admin.id and payload.account_status != "active":
        raise HTTPException(status_code=400, detail="不能暂停或禁用当前管理员账号")
    family_count = int(
        await session.scalar(
            select(func.count()).select_from(FamilyMember).where(FamilyMember.user_id == user.id)
        )
        or 0
    )
    updated = await set_user_account_status(
        session,
        target=user,
        new_status=payload.account_status,
        actor_user_id=current_admin.id,
    )
    return _user_response(updated, family_count)


@router.post(
    "/invitations",
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_invitation(
    payload: InvitationCreateRequest,
    request: Request,
    current_admin: SystemAdmin,
    session: DbSession,
) -> InvitationCreatedResponse:
    try:
        result = await create_platform_invitation(
            session,
            request.app.state.settings,
            actor=current_admin,
            expires_at=payload.expires_at,
            max_uses=payload.max_uses,
            email_constraint=str(payload.email_constraint) if payload.email_constraint else None,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail="邀请码过期时间必须晚于当前时间") from error
    public = _invitation_response(result.invitation, current_admin.display_name)
    return InvitationCreatedResponse(**public.model_dump(), invitation_code=result.plaintext_code)


@router.get("/invitations", response_model=InvitationPage)
async def admin_list_invitations(
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> InvitationPage:
    total = int(await session.scalar(select(func.count()).select_from(PlatformInvitation)) or 0)
    rows = (
        await session.execute(
            select(PlatformInvitation, User.display_name)
            .join(User, User.id == PlatformInvitation.created_by_user_id)
            .order_by(PlatformInvitation.created_at.desc(), PlatformInvitation.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return InvitationPage(
        items=[_invitation_response(row[0], row[1]) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/invitations/{invitation_id}/revoke", response_model=InvitationResponse)
async def admin_revoke_invitation(
    invitation_id: uuid.UUID,
    current_admin: SystemAdmin,
    session: DbSession,
) -> InvitationResponse:
    invitation = await revoke_platform_invitation(
        session, invitation_id=invitation_id, actor=current_admin
    )
    if invitation is None:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    creator_name = await session.scalar(
        select(User.display_name).where(User.id == invitation.created_by_user_id)
    )
    return _invitation_response(invitation, creator_name or "已删除用户")
