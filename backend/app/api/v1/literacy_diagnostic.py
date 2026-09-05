"""Child-private endpoints for the representative 1200-character literacy diagnostic."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status

from app.api.dependencies import CurrentUser, DbSession
from app.integrations.asr import (
    ASRConfigurationError,
    ASRNoSpeechError,
    ASRProviderError,
    ASRTransportError,
    DashScopeASRProvider,
    normalize_audio_content_type,
)
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
    request: Request,
) -> LiteracyDiagnosticOverviewResponse:
    await get_authorized_child(session, current_user, child_id)
    response = await literacy_diagnostic_overview(session, child_id)
    settings = request.app.state.settings
    configured = settings.literacy_asr_configured
    return response.model_copy(
        update={
            "server_asr_enabled": configured,
            "server_asr_provider": settings.literacy_asr_provider if configured else None,
            "server_asr_model": settings.literacy_asr_model if configured else None,
        }
    )


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


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
        return await get_literacy_diagnostic_session(session, child_id, assessment_session_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error


@router.post(
    "/{child_id}/literacy-diagnostic/sessions/{assessment_session_id}/audio-attempts",
    response_model=SpeechAttemptResponse,
)
async def submit_literacy_diagnostic_audio_attempt(
    child_id: uuid.UUID,
    assessment_session_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    request: Request,
    knowledge_point_id: Annotated[uuid.UUID, Form()],
    attempt_index: Annotated[int, Form(ge=1, le=3)],
    audio: Annotated[UploadFile, File()],
    capture_duration_ms: Annotated[int | None, Form(ge=0, le=10_000)] = None,
) -> SpeechAttemptResponse:
    """Transcribe one short recording without retaining the raw child audio."""

    await get_authorized_child(session, current_user, child_id)
    settings = request.app.state.settings
    if not settings.literacy_asr_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="server_asr_disabled",
        )

    # Validate the persisted diagnostic target before making a paid external
    # request. A duplicate retry returns the already preserved attempt.
    try:
        snapshot = await get_literacy_diagnostic_session(session, child_id, assessment_session_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    target = next(
        (item for item in snapshot.targets if item.knowledge_point_id == knowledge_point_id),
        None,
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Audio target is outside the persisted diagnostic sample",
        )
    if target.outcome is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Diagnostic target answered",
        )
    existing = next(
        (item for item in target.speech_attempts if item.attempt_index == attempt_index),
        None,
    )
    if existing is not None:
        return existing

    try:
        normalize_audio_content_type(audio.content_type)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from error
    max_bytes = settings.literacy_asr_max_audio_bytes
    try:
        audio_bytes = await audio.read(max_bytes + 1)
    finally:
        await audio.close()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="asr_no_speech",
        )
    if len(audio_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Diagnostic audio is too large",
        )

    provider = DashScopeASRProvider(
        api_key=settings.literacy_asr_api_key.get_secret_value(),
        model=settings.literacy_asr_model,
        base_url=settings.literacy_asr_base_url,
        timeout_seconds=settings.literacy_asr_timeout_seconds,
    )
    try:
        transcription = await provider.transcribe(audio_bytes, audio.content_type)
    except ASRNoSpeechError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="asr_no_speech",
        ) from error
    except ASRConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="server_asr_configuration_error",
        ) from error
    except ASRTransportError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="server_asr_transport_error",
        ) from error
    except ASRProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="server_asr_provider_error",
        ) from error

    # Persist only transcript + minimal metadata. The audio bytes and Base64 Data
    # URI go out of scope here and are never written to DB, MinIO, or logs.
    payload = SpeechAttemptCreate(
        knowledge_point_id=knowledge_point_id,
        attempt_index=attempt_index,
        provider=transcription.provider,
        transcript=transcription.transcript,
        confidence=None,
        confidence_available=False,
        duration_ms=capture_duration_ms,
        decision="uncertain",
        provider_metadata={
            "model": transcription.model,
            "request_id": transcription.request_id,
            "provider_latency_ms": transcription.latency_ms,
            "usage_duration_seconds": transcription.usage_duration_seconds,
            "audio_content_type": (audio.content_type or "").split(";", maxsplit=1)[0],
            "raw_audio_stored": False,
        },
    )
    try:
        return await persist_literacy_diagnostic_speech_attempt(
            session,
            child_id,
            assessment_session_id,
            current_user.id,
            payload,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
