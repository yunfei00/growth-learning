"""Central server-side household authorization checks."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Child, FamilyMember, FamilyRole, User


async def require_family_membership(
    session: AsyncSession, current_user: User, family_id: uuid.UUID
) -> FamilyMember:
    """Return membership or hide another household behind a 404 response."""
    membership = await session.scalar(
        select(FamilyMember).where(
            FamilyMember.family_id == family_id,
            FamilyMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found")
    return membership


async def require_family_admin(
    session: AsyncSession, current_user: User, family_id: uuid.UUID
) -> FamilyMember:
    """Require an administrator for household-changing operations."""
    membership = await require_family_membership(session, current_user, family_id)
    if membership.role != FamilyRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Family administrator permission required",
        )
    return membership


async def get_authorized_child(
    session: AsyncSession,
    current_user: User,
    child_id: uuid.UUID,
    *,
    admin_required: bool = False,
) -> tuple[Child, FamilyMember]:
    """Load a child only through a current user's matching family membership."""
    row = (
        await session.execute(
            select(Child, FamilyMember)
            .join(FamilyMember, FamilyMember.family_id == Child.family_id)
            .where(Child.id == child_id, FamilyMember.user_id == current_user.id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child not found")

    child, membership = row
    if admin_required and membership.role != FamilyRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Family administrator permission required",
        )
    return child, membership
