"""Serialized reading progress API."""

import uuid

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.reading_series import ReadingSeriesProgressResponse
from app.services.authorization import get_authorized_child
from app.services.reading_series import reading_series_progress

router = APIRouter(prefix="/children", tags=["reading series"])


@router.get("/{child_id}/reading-series/current", response_model=ReadingSeriesProgressResponse)
async def get_current_reading_series(
    child_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> ReadingSeriesProgressResponse:
    await get_authorized_child(session, current_user, child_id)
    response = await reading_series_progress(session, child_id)
    await session.commit()
    return response
