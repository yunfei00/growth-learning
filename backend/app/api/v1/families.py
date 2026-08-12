"""Authenticated family, membership, and nested child endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.models import Child, Family, FamilyMember, FamilyRole, User
from app.schemas.family import (
    ChildCreate,
    ChildResponse,
    FamilyCreate,
    FamilyMemberResponse,
    FamilyResponse,
    FamilyUpdate,
    MemberUserResponse,
)
from app.services.authorization import require_family_admin, require_family_membership

router = APIRouter(prefix="/families", tags=["families"])


def _family_response(family: Family, role: str) -> FamilyResponse:
    return FamilyResponse(
        id=family.id,
        name=family.name,
        current_role=role,
        created_at=family.created_at,
        updated_at=family.updated_at,
    )


@router.post("", response_model=FamilyResponse, status_code=status.HTTP_201_CREATED)
async def create_family(
    payload: FamilyCreate, current_user: CurrentUser, session: DbSession
) -> FamilyResponse:
    """Create a family and atomically grant its creator the admin role."""
    family = Family(name=payload.name)
    session.add(family)
    await session.flush()
    session.add(
        FamilyMember(
            family_id=family.id,
            user_id=current_user.id,
            role=FamilyRole.ADMIN,
        )
    )
    await session.commit()
    await session.refresh(family)
    return _family_response(family, FamilyRole.ADMIN)


@router.get("", response_model=list[FamilyResponse])
async def list_families(current_user: CurrentUser, session: DbSession) -> list[FamilyResponse]:
    """List only families joined through the current adult's membership."""
    rows = (
        await session.execute(
            select(Family, FamilyMember.role)
            .join(FamilyMember, FamilyMember.family_id == Family.id)
            .where(FamilyMember.user_id == current_user.id)
            .order_by(Family.created_at)
        )
    ).all()
    return [_family_response(family, role) for family, role in rows]


@router.get("/{family_id}", response_model=FamilyResponse)
async def get_family(
    family_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> FamilyResponse:
    """Get a family only when the current adult belongs to it."""
    membership = await require_family_membership(session, current_user, family_id)
    family = await session.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found")
    return _family_response(family, membership.role)


@router.patch("/{family_id}", response_model=FamilyResponse)
async def update_family(
    family_id: uuid.UUID,
    payload: FamilyUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> FamilyResponse:
    """Allow only a family administrator to rename the household."""
    membership = await require_family_admin(session, current_user, family_id)
    family = await session.get(Family, family_id)
    if family is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found")
    family.name = payload.name
    await session.commit()
    await session.refresh(family)
    return _family_response(family, membership.role)


@router.get("/{family_id}/members", response_model=list[FamilyMemberResponse])
async def list_family_members(
    family_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> list[FamilyMemberResponse]:
    """Allow family members to see the adults who belong to their household."""
    await require_family_membership(session, current_user, family_id)
    rows = (
        await session.execute(
            select(FamilyMember, User)
            .join(User, User.id == FamilyMember.user_id)
            .where(FamilyMember.family_id == family_id)
            .order_by(FamilyMember.created_at)
        )
    ).all()
    return [
        FamilyMemberResponse(
            id=membership.id,
            role=membership.role,
            user=MemberUserResponse.model_validate(user),
            created_at=membership.created_at,
            updated_at=membership.updated_at,
        )
        for membership, user in rows
    ]


@router.post(
    "/{family_id}/children",
    response_model=ChildResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_child(
    family_id: uuid.UUID,
    payload: ChildCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> Child:
    """Allow only a family administrator to create a child profile."""
    await require_family_admin(session, current_user, family_id)
    child = Child(family_id=family_id, **payload.model_dump())
    session.add(child)
    await session.commit()
    await session.refresh(child)
    return child


@router.get("/{family_id}/children", response_model=list[ChildResponse])
async def list_children(
    family_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> list[Child]:
    """List the real child profiles visible inside a family boundary."""
    await require_family_membership(session, current_user, family_id)
    return list(
        await session.scalars(
            select(Child).where(Child.family_id == family_id).order_by(Child.created_at)
        )
    )
