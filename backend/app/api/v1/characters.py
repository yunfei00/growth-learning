"""Authenticated read-only access to enabled canonical Chinese characters."""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.knowledge import CharacterPage, CharacterResponse
from app.services.character_catalog import get_character, list_characters, to_response

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("", response_model=CharacterPage)
async def list_enabled_characters(
    _: CurrentUser,
    session: DbSession,
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CharacterPage:
    return await list_characters(
        session,
        search=search,
        enabled=True,
        page=page,
        page_size=page_size,
        public_only=True,
    )


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_enabled_character(
    character_id: uuid.UUID, _: CurrentUser, session: DbSession
) -> CharacterResponse:
    row = await get_character(session, character_id, enabled_only=True)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    return to_response(*row)
