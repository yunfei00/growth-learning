"""System-administrator routes for the reusable science experiment catalog."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DbSession, SystemAdmin, require_system_admin
from app.models import ExperimentMaterial
from app.schemas.science import (
    MaterialResponse,
    ScienceExperimentCreate,
    ScienceExperimentPage,
    ScienceExperimentResponse,
    ScienceExperimentUpdate,
    ScienceImportReport,
)
from app.services.science_catalog import (
    create_science_experiment,
    get_science_experiment,
    import_starter_science_experiments,
    list_science_experiments,
    science_experiment_response,
    update_science_experiment,
)

router = APIRouter(
    prefix="/admin/science",
    tags=["science administration"],
    dependencies=[Depends(require_system_admin)],
)


@router.get("/experiments", response_model=ScienceExperimentPage)
async def admin_list_science_experiments(
    session: DbSession,
    search: str | None = Query(default=None, max_length=120),
    status_filter: str | None = Query(
        default=None, alias="status", pattern="^(draft|enabled|archived)$"
    ),
    difficulty: str | None = Query(default=None, pattern="^(intro|explore|advanced)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ScienceExperimentPage:
    return await list_science_experiments(
        session,
        search=search,
        status=status_filter,
        difficulty=difficulty,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/experiments",
    response_model=ScienceExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_science_experiment(
    payload: ScienceExperimentCreate,
    session: DbSession,
    admin: SystemAdmin,
) -> ScienceExperimentResponse:
    try:
        experiment, _ = await create_science_experiment(session, payload, actor_user_id=admin.id)
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Science experiment already exists") from error
    except ValueError as error:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    return await science_experiment_response(session, experiment)


@router.get("/experiments/{experiment_id}", response_model=ScienceExperimentResponse)
async def admin_get_science_experiment(
    experiment_id: uuid.UUID, session: DbSession
) -> ScienceExperimentResponse:
    experiment = await get_science_experiment(session, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Science experiment not found")
    return await science_experiment_response(session, experiment)


@router.patch("/experiments/{experiment_id}", response_model=ScienceExperimentResponse)
async def admin_update_science_experiment(
    experiment_id: uuid.UUID,
    payload: ScienceExperimentUpdate,
    session: DbSession,
    admin: SystemAdmin,
) -> ScienceExperimentResponse:
    experiment = await get_science_experiment(session, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Science experiment not found")
    try:
        await update_science_experiment(session, experiment, payload, actor_user_id=admin.id)
    except (IntegrityError, ValueError) as error:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    return await science_experiment_response(session, experiment)


@router.get("/materials", response_model=list[MaterialResponse])
async def admin_list_materials(session: DbSession) -> list[MaterialResponse]:
    materials = list(
        (
            await session.scalars(
                select(ExperimentMaterial).order_by(
                    ExperimentMaterial.category, ExperimentMaterial.name
                )
            )
        ).all()
    )
    return [MaterialResponse.model_validate(item) for item in materials]


@router.post("/import-starter", response_model=ScienceImportReport)
async def admin_import_starter_science(session: DbSession) -> ScienceImportReport:
    result = await import_starter_science_experiments(session)
    return ScienceImportReport(**result.__dict__)
