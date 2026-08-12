"""Authorized child profile endpoints."""

import uuid

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DbSession
from app.models import Child
from app.schemas.family import ChildResponse, ChildUpdate
from app.services.authorization import get_authorized_child

router = APIRouter(prefix="/children", tags=["children"])


@router.get("/{child_id}", response_model=ChildResponse)
async def get_child(child_id: uuid.UUID, current_user: CurrentUser, session: DbSession) -> Child:
    """Return a child only through the current user's family membership."""
    child, _ = await get_authorized_child(session, current_user, child_id)
    return child


@router.patch("/{child_id}", response_model=ChildResponse)
async def update_child(
    child_id: uuid.UUID,
    payload: ChildUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> Child:
    """Allow only a family administrator to update a child profile."""
    child, _ = await get_authorized_child(session, current_user, child_id, admin_required=True)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(child, field, value)
    await session.commit()
    await session.refresh(child)
    return child
