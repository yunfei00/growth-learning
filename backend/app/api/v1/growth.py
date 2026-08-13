"""Household-private growth archive, reports, books, media, and exports."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.integrations.ai.base import AIProvider
from app.integrations.ai.factory import build_ai_provider
from app.integrations.object_storage import PrivateObjectStorage, build_private_object_storage
from app.models import (
    ExportJob,
    ExportJobStatus,
    GrowthBook,
    GrowthBookVersion,
    GrowthEvent,
    GrowthReport,
    GrowthReportVersion,
)
from app.schemas.growth import (
    ExportJobResponse,
    ExportRequest,
    GrowthBookCreate,
    GrowthBookSummary,
    GrowthBookVersionResponse,
    GrowthEventCreate,
    GrowthEventPage,
    GrowthEventResponse,
    GrowthProjectionResult,
    GrowthReportGenerate,
    GrowthReportSummary,
    GrowthReportVersionResponse,
)
from app.services.authorization import get_authorized_child, require_family_admin
from app.services.family_export import create_family_export
from app.services.growth_books import (
    create_growth_book_version,
    growth_book_response,
    list_growth_books,
)
from app.services.growth_media import get_private_growth_media, persist_growth_media
from app.services.growth_reports import (
    generate_growth_report,
    list_growth_reports,
    report_version_response,
)
from app.services.growth_timeline import (
    POLICY_VERSION,
    create_manual_growth_event,
    event_response,
    list_growth_events,
    project_growth_events,
)
from app.services.science_media import ScienceMediaValidationError

router = APIRouter(tags=["growth archive"])


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def get_growth_storage(request: Request) -> PrivateObjectStorage:
    return build_private_object_storage(request.app.state.settings)


def get_growth_ai_provider(request: Request) -> AIProvider:
    return build_ai_provider(request.app.state.settings)


GrowthStorage = Annotated[PrivateObjectStorage, Depends(get_growth_storage)]
GrowthAIProvider = Annotated[AIProvider, Depends(get_growth_ai_provider)]
GrowthUpload = Annotated[UploadFile, File()]


@router.get("/children/{child_id}/growth/events", response_model=GrowthEventPage)
async def get_timeline(
    child_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    category: str | None = Query(
        default=None,
        pattern="^(learning|assessment|reading|science|family|original_words|achievement|report)$",
    ),
    year: int | None = Query(default=None, ge=2000, le=2200),
    month: int | None = Query(default=None, ge=1, le=12),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
) -> GrowthEventPage:
    await get_authorized_child(session, current_user, child_id)
    await project_growth_events(session, child_id)
    return await list_growth_events(
        session, child_id, category=category, year=year, month=month, page=page, page_size=page_size
    )


@router.get("/children/{child_id}/growth/recent", response_model=list[GrowthEventResponse])
async def get_recent_growth(
    child_id: uuid.UUID, session: DbSession, current_user: CurrentUser
) -> list[GrowthEventResponse]:
    await get_authorized_child(session, current_user, child_id)
    await project_growth_events(session, child_id)
    page = await list_growth_events(session, child_id, page_size=5)
    return page.items


@router.post(
    "/children/{child_id}/growth/events", response_model=GrowthEventResponse, status_code=201
)
async def post_manual_growth(
    child_id: uuid.UUID,
    payload: GrowthEventCreate,
    session: DbSession,
    current_user: CurrentUser,
) -> GrowthEventResponse:
    _, membership = await get_authorized_child(session, current_user, child_id)
    event = await create_manual_growth_event(
        session,
        child_id=child_id,
        actor_user_id=current_user.id,
        family_role=membership.role,
        payload=payload,
    )
    return await event_response(session, event)


@router.post(
    "/children/{child_id}/growth/events/{event_id}/media",
    response_model=GrowthEventResponse,
    status_code=201,
)
async def upload_growth_media(
    child_id: uuid.UUID,
    event_id: uuid.UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
    storage: GrowthStorage,
    file: GrowthUpload,
) -> GrowthEventResponse:
    child, _ = await get_authorized_child(session, current_user, child_id)
    event = await session.scalar(
        select(GrowthEvent).where(
            GrowthEvent.id == event_id,
            GrowthEvent.child_id == child_id,
            GrowthEvent.actor_user_id == current_user.id,
            GrowthEvent.source_type != "system",
        )
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Growth event not found")
    settings = request.app.state.settings
    read_limit = max(
        settings.science_image_max_bytes,
        settings.science_video_max_bytes,
        settings.science_audio_max_bytes,
    )
    content = await file.read(read_limit + 1)
    try:
        await persist_growth_media(
            session,
            storage,
            settings=settings,
            event=event,
            family_id=child.family_id,
            uploader_user_id=current_user.id,
            filename=file.filename,
            mime_type=file.content_type,
            content=content,
        )
    except ScienceMediaValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return await event_response(session, event)


@router.get(
    "/children/{child_id}/growth/events/{event_id}/media/{media_id}/content",
    response_class=Response,
)
async def stream_growth_media(
    child_id: uuid.UUID,
    event_id: uuid.UUID,
    media_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    storage: GrowthStorage,
) -> Response:
    await get_authorized_child(session, current_user, child_id)
    asset = await get_private_growth_media(
        session, child_id=child_id, event_id=event_id, media_id=media_id
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Growth media not found")
    return Response(
        content=await storage.read(asset.object_key),
        media_type=asset.mime_type,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/children/{child_id}/growth/rebuild", response_model=GrowthProjectionResult)
async def rebuild_child_growth(
    child_id: uuid.UUID, session: DbSession, current_user: CurrentUser
) -> GrowthProjectionResult:
    await get_authorized_child(session, current_user, child_id, admin_required=True)
    result = await project_growth_events(session, child_id)
    return GrowthProjectionResult(
        created=result.created, existing=result.existing, policy_version=POLICY_VERSION
    )


@router.post(
    "/children/{child_id}/growth/reports",
    response_model=GrowthReportVersionResponse,
    status_code=201,
)
async def generate_report(
    child_id: uuid.UUID,
    payload: GrowthReportGenerate,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
    provider: GrowthAIProvider,
) -> GrowthReportVersionResponse:
    await get_authorized_child(session, current_user, child_id, admin_required=True)
    await project_growth_events(session, child_id)
    settings = request.app.state.settings
    configured = bool(
        settings.ai_provider != "disabled"
        and settings.ai_api_key.get_secret_value()
        and settings.ai_model
    )
    version = await generate_growth_report(
        session,
        child_id=child_id,
        actor_user_id=current_user.id,
        payload=payload,
        provider=provider if configured and payload.include_ai_narrative else None,
    )
    return await report_version_response(session, version)


@router.get("/children/{child_id}/growth/reports", response_model=list[GrowthReportSummary])
async def get_reports(
    child_id: uuid.UUID, session: DbSession, current_user: CurrentUser
) -> list[GrowthReportSummary]:
    await get_authorized_child(session, current_user, child_id, admin_required=True)
    return await list_growth_reports(session, child_id)


@router.get(
    "/children/{child_id}/growth/reports/{report_id}", response_model=GrowthReportVersionResponse
)
async def get_report(
    child_id: uuid.UUID,
    report_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    version: int | None = Query(default=None, ge=1),
) -> GrowthReportVersionResponse:
    await get_authorized_child(session, current_user, child_id, admin_required=True)
    report = await session.scalar(
        select(GrowthReport).where(GrowthReport.id == report_id, GrowthReport.child_id == child_id)
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Growth report not found")
    query = select(GrowthReportVersion).where(GrowthReportVersion.report_id == report_id)
    query = (
        query.where(GrowthReportVersion.version_number == version)
        if version
        else query.order_by(GrowthReportVersion.version_number.desc()).limit(1)
    )
    report_version = await session.scalar(query)
    if report_version is None:
        raise HTTPException(status_code=404, detail="Growth report version not found")
    return await report_version_response(session, report_version)


@router.post(
    "/children/{child_id}/growth/books",
    response_model=GrowthBookVersionResponse,
    status_code=201,
)
async def create_book(
    child_id: uuid.UUID,
    payload: GrowthBookCreate,
    session: DbSession,
    current_user: CurrentUser,
) -> GrowthBookVersionResponse:
    await get_authorized_child(session, current_user, child_id, admin_required=True)
    try:
        version = await create_growth_book_version(
            session, child_id=child_id, actor_user_id=current_user.id, payload=payload
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return await growth_book_response(session, version)


@router.get("/children/{child_id}/growth/books", response_model=list[GrowthBookSummary])
async def get_books(
    child_id: uuid.UUID, session: DbSession, current_user: CurrentUser
) -> list[GrowthBookSummary]:
    await get_authorized_child(session, current_user, child_id, admin_required=True)
    return await list_growth_books(session, child_id)


@router.get("/children/{child_id}/growth/books/{book_id}", response_model=GrowthBookVersionResponse)
async def get_book(
    child_id: uuid.UUID,
    book_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    version: int | None = Query(default=None, ge=1),
) -> GrowthBookVersionResponse:
    await get_authorized_child(session, current_user, child_id, admin_required=True)
    book = await session.scalar(
        select(GrowthBook).where(GrowthBook.id == book_id, GrowthBook.child_id == child_id)
    )
    if book is None:
        raise HTTPException(status_code=404, detail="Growth book not found")
    query = select(GrowthBookVersion).where(GrowthBookVersion.growth_book_id == book_id)
    query = (
        query.where(GrowthBookVersion.version_number == version)
        if version
        else query.order_by(GrowthBookVersion.version_number.desc()).limit(1)
    )
    book_version = await session.scalar(query)
    if book_version is None:
        raise HTTPException(status_code=404, detail="Growth book version not found")
    return await growth_book_response(session, book_version)


def _export_response(job: ExportJob) -> ExportJobResponse:
    available = (
        job.status == ExportJobStatus.COMPLETED
        and job.expires_at
        and _utc(job.expires_at) > datetime.now(UTC)
    )
    return ExportJobResponse(
        **{
            column.name: getattr(job, column.name)
            for column in job.__table__.columns
            if column.name not in {"object_key", "manifest_snapshot"}
        },
        download_url=f"/api/v1/families/{job.family_id}/exports/{job.id}/download"
        if available
        else None,
    )


@router.post("/families/{family_id}/exports", response_model=ExportJobResponse, status_code=201)
async def request_export(
    family_id: uuid.UUID,
    payload: ExportRequest,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
    storage: GrowthStorage,
) -> ExportJobResponse:
    await require_family_admin(session, current_user, family_id)
    if payload.child_id:
        child, _ = await get_authorized_child(
            session, current_user, payload.child_id, admin_required=True
        )
        if child.family_id != family_id:
            raise HTTPException(status_code=404, detail="Child not found")
    try:
        job = await create_family_export(
            session,
            storage,
            family_id=family_id,
            child_id=payload.child_id,
            requested_by_user_id=current_user.id,
            ttl_seconds=request.app.state.settings.export_download_ttl_seconds,
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail="Family export failed") from error
    return _export_response(job)


@router.get("/families/{family_id}/exports/{job_id}", response_model=ExportJobResponse)
async def get_export(
    family_id: uuid.UUID,
    job_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> ExportJobResponse:
    await require_family_admin(session, current_user, family_id)
    job = await session.scalar(
        select(ExportJob).where(ExportJob.id == job_id, ExportJob.family_id == family_id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Export job not found")
    return _export_response(job)


@router.get("/families/{family_id}/exports/{job_id}/download", response_class=StreamingResponse)
async def download_export(
    family_id: uuid.UUID,
    job_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    storage: GrowthStorage,
) -> StreamingResponse:
    await require_family_admin(session, current_user, family_id)
    job = await session.scalar(
        select(ExportJob).where(ExportJob.id == job_id, ExportJob.family_id == family_id)
    )
    if job is None or job.status != ExportJobStatus.COMPLETED or not job.object_key:
        raise HTTPException(status_code=404, detail="Export file not found")
    if not job.expires_at or _utc(job.expires_at) <= datetime.now(UTC):
        job.status = ExportJobStatus.EXPIRED
        await session.commit()
        raise HTTPException(status_code=410, detail="Export download has expired")
    return StreamingResponse(
        storage.stream(job.object_key),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="growth-learning-export-{job.id}.zip"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
