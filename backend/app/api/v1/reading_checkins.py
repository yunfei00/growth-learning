"""Daily reading check-in and child-initiated reading-help routes."""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.reading_checkin import (
    ReadingCheckinSummaryResponse,
    ReadingHelpEventCreate,
    ReadingHelpEventResponse,
)
from app.services.authorization import get_authorized_child
from app.services.reading_checkins import reading_checkin_summary, record_reading_help

router = APIRouter(prefix="/children", tags=["reading check-ins"])


@router.post(
    "/{child_id}/reading-sessions/{reading_session_id}/help-events",
    response_model=ReadingHelpEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_help_event(
    child_id: uuid.UUID,
    reading_session_id: uuid.UUID,
    payload: ReadingHelpEventCreate,
    session: DbSession,
    current_user: CurrentUser,
) -> ReadingHelpEventResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await record_reading_help(
            session,
            child_id=child_id,
            reading_session_id=reading_session_id,
            payload=payload,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{child_id}/reading-checkins", response_model=ReadingCheckinSummaryResponse)
async def get_reading_checkins(
    child_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    today: date | None = Query(default=None),
) -> ReadingCheckinSummaryResponse:
    await get_authorized_child(session, current_user, child_id)
    resolved_today = today or date.today()
    resolved_to = to_date or resolved_today
    resolved_from = from_date or (resolved_to - timedelta(days=30))
    try:
        return await reading_checkin_summary(
            session,
            child_id=child_id,
            from_date=resolved_from,
            to_date=resolved_to,
            today=resolved_today,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
