"""Household-private Weekend Science Lab routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.integrations.ai.base import AIProvider
from app.integrations.ai.factory import build_ai_provider
from app.integrations.object_storage import PrivateObjectStorage, build_private_object_storage
from app.models import (
    ExperimentSessionStatus,
    FamilyRole,
    ScienceExperiment,
    ScienceExperimentStatus,
)
from app.schemas.science import (
    ExperimentCompleteRequest,
    ExperimentEvidenceBatch,
    ExperimentEvidenceResponse,
    ExperimentGrowthCardResponse,
    ExperimentRecommendationResponse,
    ExperimentSessionCreate,
    ExperimentSessionPage,
    ExperimentSessionResponse,
    ExperimentSessionUpdate,
    ExperimentStoryGenerationRequest,
    FamilyMaterialBatchUpdate,
    FamilyMaterialResponse,
    ScienceExperimentPage,
    ScienceExperimentResponse,
)
from app.schemas.story import StoryGenerationRequest, StoryGenerationResponse
from app.services.authorization import (
    get_authorized_child,
    require_family_admin,
    require_family_membership,
)
from app.services.science_catalog import list_science_experiments, science_experiment_response
from app.services.science_learning import (
    append_experiment_evidence,
    complete_experiment_session,
    create_or_resume_experiment_session,
    experiment_growth_card,
    experiment_session_response,
    get_private_experiment_session,
    list_experiment_sessions,
    list_family_material_inventory,
    recommend_science_experiments,
    update_experiment_session,
    update_family_material_inventory,
)
from app.services.science_media import (
    ScienceMediaValidationError,
    get_private_media_asset,
    persist_experiment_media,
)
from app.services.story_generation import StoryGenerationError, generate_story
from app.services.story_reading import story_version_response

router = APIRouter(tags=["weekend science lab"])


def get_science_storage(request: Request) -> PrivateObjectStorage:
    return build_private_object_storage(request.app.state.settings)


def get_science_ai_provider(request: Request) -> AIProvider:
    return build_ai_provider(request.app.state.settings)


ScienceStorage = Annotated[PrivateObjectStorage, Depends(get_science_storage)]
ScienceAIProvider = Annotated[AIProvider, Depends(get_science_ai_provider)]
ScienceUpload = Annotated[UploadFile, File()]


@router.get("/science/experiments", response_model=ScienceExperimentPage)
async def public_science_catalog(
    session: DbSession,
    current_user: CurrentUser,
    search: str | None = Query(default=None, max_length=120),
    difficulty: str | None = Query(default=None, pattern="^(intro|explore|advanced)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ScienceExperimentPage:
    del current_user
    return await list_science_experiments(
        session,
        search=search,
        status=ScienceExperimentStatus.ENABLED,
        difficulty=difficulty,
        page=page,
        page_size=page_size,
        system_only=True,
    )


@router.get("/science/experiments/{experiment_id}", response_model=ScienceExperimentResponse)
async def public_science_experiment(
    experiment_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> ScienceExperimentResponse:
    del current_user
    experiment = await session.scalar(
        select(ScienceExperiment).where(
            ScienceExperiment.id == experiment_id,
            ScienceExperiment.status == ScienceExperimentStatus.ENABLED,
            ScienceExperiment.owner_family_id.is_(None),
        )
    )
    if experiment is None:
        raise HTTPException(status_code=404, detail="Science experiment not found")
    return await science_experiment_response(session, experiment)


@router.get("/families/{family_id}/science/materials", response_model=list[FamilyMaterialResponse])
async def get_family_materials(
    family_id: uuid.UUID, session: DbSession, current_user: CurrentUser
) -> list[FamilyMaterialResponse]:
    await require_family_membership(session, current_user, family_id)
    return await list_family_material_inventory(session, family_id)


@router.put("/families/{family_id}/science/materials", response_model=list[FamilyMaterialResponse])
async def put_family_materials(
    family_id: uuid.UUID,
    payload: FamilyMaterialBatchUpdate,
    session: DbSession,
    current_user: CurrentUser,
) -> list[FamilyMaterialResponse]:
    await require_family_admin(session, current_user, family_id)
    try:
        return await update_family_material_inventory(
            session,
            family_id=family_id,
            actor_user_id=current_user.id,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get(
    "/children/{child_id}/science/recommendations",
    response_model=list[ExperimentRecommendationResponse],
)
async def get_science_recommendations(
    child_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=6, ge=1, le=20),
) -> list[ExperimentRecommendationResponse]:
    child, _ = await get_authorized_child(session, current_user, child_id)
    return await recommend_science_experiments(session, child, limit=limit)


@router.post(
    "/children/{child_id}/experiment-sessions",
    response_model=ExperimentSessionResponse,
    status_code=201,
)
async def start_experiment_session(
    child_id: uuid.UUID,
    payload: ExperimentSessionCreate,
    session: DbSession,
    current_user: CurrentUser,
) -> ExperimentSessionResponse:
    child, _ = await get_authorized_child(session, current_user, child_id)
    try:
        experiment_session = await create_or_resume_experiment_session(
            session,
            child=child,
            actor_user_id=current_user.id,
            payload=payload,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return await experiment_session_response(session, experiment_session)


@router.get("/children/{child_id}/experiment-sessions", response_model=ExperimentSessionPage)
async def get_experiment_history(
    child_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ExperimentSessionPage:
    await get_authorized_child(session, current_user, child_id)
    return await list_experiment_sessions(session, child_id, page=page, page_size=page_size)


@router.get(
    "/children/{child_id}/experiment-sessions/{experiment_session_id}",
    response_model=ExperimentSessionResponse,
)
async def get_experiment_session(
    child_id: uuid.UUID,
    experiment_session_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> ExperimentSessionResponse:
    await get_authorized_child(session, current_user, child_id)
    experiment_session = await get_private_experiment_session(
        session, child_id, experiment_session_id
    )
    if experiment_session is None:
        raise HTTPException(status_code=404, detail="Experiment session not found")
    return await experiment_session_response(session, experiment_session)


@router.patch(
    "/children/{child_id}/experiment-sessions/{experiment_session_id}",
    response_model=ExperimentSessionResponse,
)
async def patch_experiment_session(
    child_id: uuid.UUID,
    experiment_session_id: uuid.UUID,
    payload: ExperimentSessionUpdate,
    session: DbSession,
    current_user: CurrentUser,
) -> ExperimentSessionResponse:
    _, membership = await get_authorized_child(session, current_user, child_id)
    experiment_session = await get_private_experiment_session(
        session, child_id, experiment_session_id
    )
    if experiment_session is None:
        raise HTTPException(status_code=404, detail="Experiment session not found")
    try:
        await update_experiment_session(
            session,
            experiment_session,
            payload,
            can_manage_parent_note=membership.role == FamilyRole.ADMIN,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return await experiment_session_response(session, experiment_session)


@router.post(
    "/children/{child_id}/experiment-sessions/{experiment_session_id}/evidence",
    response_model=list[ExperimentEvidenceResponse],
)
async def record_experiment_evidence(
    child_id: uuid.UUID,
    experiment_session_id: uuid.UUID,
    payload: ExperimentEvidenceBatch,
    session: DbSession,
    current_user: CurrentUser,
) -> list[ExperimentEvidenceResponse]:
    await get_authorized_child(session, current_user, child_id)
    experiment_session = await get_private_experiment_session(
        session, child_id, experiment_session_id
    )
    if experiment_session is None:
        raise HTTPException(status_code=404, detail="Experiment session not found")
    try:
        evidence = await append_experiment_evidence(
            session,
            experiment_session=experiment_session,
            child_id=child_id,
            actor_user_id=current_user.id,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return [ExperimentEvidenceResponse.model_validate(item) for item in evidence]


@router.post(
    "/children/{child_id}/experiment-sessions/{experiment_session_id}/media",
    response_model=ExperimentSessionResponse,
    status_code=201,
)
async def upload_experiment_media(
    child_id: uuid.UUID,
    experiment_session_id: uuid.UUID,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
    storage: ScienceStorage,
    file: ScienceUpload,
) -> ExperimentSessionResponse:
    child, _ = await get_authorized_child(session, current_user, child_id)
    experiment_session = await get_private_experiment_session(
        session, child_id, experiment_session_id
    )
    if experiment_session is None:
        raise HTTPException(status_code=404, detail="Experiment session not found")
    if experiment_session.status != ExperimentSessionStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Experiment session is not in progress")
    settings = request.app.state.settings
    read_limit = max(
        settings.science_image_max_bytes,
        settings.science_video_max_bytes,
        settings.science_audio_max_bytes,
    )
    content = await file.read(read_limit + 1)
    try:
        await persist_experiment_media(
            session,
            storage,
            settings=settings,
            experiment_session=experiment_session,
            family_id=child.family_id,
            uploader_user_id=current_user.id,
            filename=file.filename,
            mime_type=file.content_type,
            content=content,
        )
    except ScienceMediaValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return await experiment_session_response(session, experiment_session)


@router.get(
    "/children/{child_id}/experiment-sessions/{experiment_session_id}/media/{media_id}/content",
    response_class=Response,
)
async def stream_experiment_media(
    child_id: uuid.UUID,
    experiment_session_id: uuid.UUID,
    media_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    storage: ScienceStorage,
) -> Response:
    await get_authorized_child(session, current_user, child_id)
    asset = await get_private_media_asset(
        session,
        child_id=child_id,
        experiment_session_id=experiment_session_id,
        media_id=media_id,
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Experiment media not found")
    content = await storage.read(asset.object_key)
    return Response(
        content=content,
        media_type=asset.mime_type,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


@router.post(
    "/children/{child_id}/experiment-sessions/{experiment_session_id}/complete",
    response_model=ExperimentSessionResponse,
)
async def finish_experiment_session(
    child_id: uuid.UUID,
    experiment_session_id: uuid.UUID,
    payload: ExperimentCompleteRequest,
    session: DbSession,
    current_user: CurrentUser,
) -> ExperimentSessionResponse:
    _, membership = await get_authorized_child(session, current_user, child_id)
    if payload.parent_note is not None and membership.role != FamilyRole.ADMIN:
        raise HTTPException(status_code=403, detail="Family administrator permission required")
    experiment_session = await get_private_experiment_session(
        session, child_id, experiment_session_id
    )
    if experiment_session is None:
        raise HTTPException(status_code=404, detail="Experiment session not found")
    try:
        await complete_experiment_session(
            session,
            experiment_session,
            actor_user_id=current_user.id,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return await experiment_session_response(session, experiment_session)


@router.get(
    "/children/{child_id}/experiment-sessions/{experiment_session_id}/growth-card",
    response_model=ExperimentGrowthCardResponse,
)
async def get_experiment_growth_card(
    child_id: uuid.UUID,
    experiment_session_id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> ExperimentGrowthCardResponse:
    await get_authorized_child(session, current_user, child_id)
    experiment_session = await get_private_experiment_session(
        session, child_id, experiment_session_id
    )
    if experiment_session is None:
        raise HTTPException(status_code=404, detail="Experiment session not found")
    try:
        return await experiment_growth_card(session, experiment_session)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/children/{child_id}/experiment-sessions/{experiment_session_id}/generate-story",
    response_model=StoryGenerationResponse,
    status_code=201,
)
async def generate_experiment_story(
    child_id: uuid.UUID,
    experiment_session_id: uuid.UUID,
    payload: ExperimentStoryGenerationRequest,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
    provider: ScienceAIProvider,
) -> StoryGenerationResponse:
    child, _ = await get_authorized_child(session, current_user, child_id, admin_required=True)
    experiment_session = await get_private_experiment_session(
        session, child_id, experiment_session_id
    )
    if experiment_session is None:
        raise HTTPException(status_code=404, detail="Experiment session not found")
    if experiment_session.status != ExperimentSessionStatus.COMPLETED:
        raise HTTPException(
            status_code=409, detail="Complete the experiment before generating a story"
        )
    settings = request.app.state.settings
    configured = bool(
        settings.ai_provider != "disabled"
        and settings.ai_api_key.get_secret_value()
        and settings.ai_model
    )
    if not configured:
        raise HTTPException(status_code=503, detail="AI 服务尚未配置")
    snapshot = experiment_session.experiment_snapshot
    context = {
        "template_title": str(snapshot.get("title", "科学实验")),
        "guiding_question": str(snapshot.get("guiding_question", "")),
        "expected_phenomenon": str(snapshot.get("expected_phenomenon", "")),
    }
    story_payload = StoryGenerationRequest(
        theme="science",
        custom_theme=f"{context['template_title']}实验",
        difficulty=payload.difficulty,
        target_knowledge_point_ids=payload.target_knowledge_point_ids,
        request_key=payload.request_key,
    )
    try:
        run, version = await generate_story(
            session,
            child=child,
            requested_by_user_id=current_user.id,
            payload=story_payload,
            provider=provider,
            provider_name=settings.ai_provider,
            configured_model=settings.ai_model,
            max_attempts=settings.ai_story_max_attempts,
            source_experiment_session_id=experiment_session.id,
            experience_context=context,
        )
    except StoryGenerationError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return StoryGenerationResponse(
        generation_run_id=run.id,
        status="succeeded",
        attempt_count=run.attempt_count,
        version=await story_version_response(session, child_id, version),
    )
