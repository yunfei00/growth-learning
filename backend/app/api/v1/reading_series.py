"""Serialized reading progress API."""

import uuid

from fastapi import APIRouter, HTTPException

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.reading_series import (
    ReadingSeriesEpisodeOpenResponse,
    ReadingSeriesProgressResponse,
)
from app.services.authorization import get_authorized_child
from app.services.reading_series import materialize_series_episode, reading_series_progress

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


@router.post(
    "/{child_id}/reading-series/current/episodes/{episode_number}/open",
    response_model=ReadingSeriesEpisodeOpenResponse,
)
async def open_reading_series_episode(
    child_id: uuid.UUID,
    episode_number: int,
    session: DbSession,
    current_user: CurrentUser,
) -> ReadingSeriesEpisodeOpenResponse:
    """Make any day readable without changing the official daily task."""

    await get_authorized_child(session, current_user, child_id)
    try:
        _, episode, version = await materialize_series_episode(
            session,
            child_id,
            episode_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return ReadingSeriesEpisodeOpenResponse(
        episode_number=episode.episode_number,
        story_version_id=version.id,
    )
