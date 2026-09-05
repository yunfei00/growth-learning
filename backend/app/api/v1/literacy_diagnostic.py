"""Child-private endpoints for the representative 1200-character literacy diagnostic."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.learning import SpeechAttemptCreate, SpeechAttemptResponse
from app.schemas.literacy_diagnostic import (
    LiteracyDiagnosticBatchSubmit,
    LiteracyDiagnosticHistoryEntry,
    LiteracyDiagnosticOverviewResponse,
    LiteracyDiagnosticSessionResponse,
)
from app.services.authorization import get_authorized_child
from app.services.literacy_diagnostic import (
    get_literacy_diagnostic_session,
    literacy_diagnostic_history,
    literacy_diagnostic_overview,
    persist_literacy_diagnostic_speech_attempt,
    start_or_resume_literacy_diagnostic,
    submit_literacy_diagnostic_items,
)

router = APIRouter(prefix="/children", tags=["literacy diagnostic"])


@router.get(
    "/{child_id}/literacy-diagnostic/overview",
    response_model=LiteracyDiagnosticOverviewResponse,
)
async def get_literacy_diagnostic_overview(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> LiteracyDiagnosticOverviewResponse:
    await get_authorized_child(session, current_user, child_id)
    return await literacy_diagnostic_overview(session, child_id)


@router.get(
    "/{child_id}/literacy-diagnostic/history",
    response_model=list[LiteracyDiagnosticHistoryEntry],
)
async def get_literacy_diagnostic_history(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[LiteracyDiagnosticHistoryEntry]:
    await get_authorized_child(session, current_user, child_id)
    return await literacy_diagnostic_history(session, child_id, limit=limit)


@router.post(
    "/{child_id}/literacy-diagnostic/start",
    response_model=LiteracyDiagnosticSessionResponse,
)
async def start_literacy_diagnostic(
    child_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> LiteracyDiagnosticSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await start_or_resume_literacy_diagnostic(session, child_id, current_user.id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error


@router.get(
    "/{child_id}/literacy-diagnostic/sessions/{assessment_session_id}",
    response_model=LiteracyDiagnosticSessionResponse,
)
async def get_literacy_diagnostic_session_detail(
    child_id: uuid.UUID,
    assessment_session_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> LiteracyDiagnosticSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await get_literacy_diagnostic_session(
            session, child_id, assessment_session_id
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error


@router.post(
    "/{child_id}/literacy-diagnostic/sessions/{assessment_session_id}/items",
    response_model=LiteracyDiagnosticSessionResponse,
)
async def submit_literacy_diagnostic(
    child_id: uuid.UUID,
    assessment_session_id: uuid.UUID,
    payload: LiteracyDiagnosticBatchSubmit,
    current_user: CurrentUser,
    session: DbSession,
) -> LiteracyDiagnosticSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await submit_literacy_diagnostic_items(
            session,
            child_id,
            assessment_session_id,
            current_user.id,
            payload,
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error


@router.post(
    "/{child_id}/literacy-diagnostic/sessions/{assessment_session_id}/speech-attempts",
    response_model=SpeechAttemptResponse,
)
async def submit_literacy_diagnostic_speech_attempt(
    child_id: uuid.UUID,
    assessment_session_id: uuid.UUID,
    payload: SpeechAttemptCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> SpeechAttemptResponse:
    await get_authorized_child(session, current_user, child_id)
    try:
        return await persist_literacy_diagnostic_speech_attempt(
            session,
            child_id,
            assessment_session_id,
            current_user.id,
            payload,
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
