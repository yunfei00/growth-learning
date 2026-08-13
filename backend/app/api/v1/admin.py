"""System-administrator APIs for platform data and the knowledge catalog."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DbSession, require_system_admin
from app.models import (
    Child,
    ChineseCharacter,
    Family,
    KnowledgePoint,
    KnowledgeRelation,
    ScienceExperiment,
    User,
)
from app.schemas.knowledge import (
    AdminOverviewResponse,
    BulkCharacterImport,
    CharacterCreate,
    CharacterPage,
    CharacterResponse,
    CharacterUpdate,
    ImportReport,
    KnowledgeRelationCreate,
    KnowledgeRelationResponse,
)
from app.services.character_catalog import (
    create_character,
    get_character,
    import_characters,
    import_starter_relations,
    list_characters,
    load_starter_dataset,
    to_response,
)

router = APIRouter(
    prefix="/admin",
    tags=["system administration"],
    dependencies=[Depends(require_system_admin)],
)


@router.get("/overview", response_model=AdminOverviewResponse)
async def get_overview(session: DbSession) -> AdminOverviewResponse:
    """Return live database counts without exposing household records."""
    return AdminOverviewResponse(
        users=int(await session.scalar(select(func.count()).select_from(User)) or 0),
        families=int(await session.scalar(select(func.count()).select_from(Family)) or 0),
        children=int(await session.scalar(select(func.count()).select_from(Child)) or 0),
        characters=int(
            await session.scalar(select(func.count()).select_from(ChineseCharacter)) or 0
        ),
        science_experiments=int(
            await session.scalar(select(func.count()).select_from(ScienceExperiment)) or 0
        ),
    )


@router.get("/characters", response_model=CharacterPage)
async def admin_list_characters(
    session: DbSession,
    search: str | None = Query(default=None, max_length=120),
    enabled: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CharacterPage:
    return await list_characters(
        session,
        search=search,
        enabled=enabled,
        page=page,
        page_size=page_size,
    )


@router.post("/characters", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_character(payload: CharacterCreate, session: DbSession) -> CharacterResponse:
    try:
        point, character = await create_character(session, payload)
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Character already exists",
        ) from error
    return to_response(point, character)


@router.get("/characters/{character_id}", response_model=CharacterResponse)
async def admin_get_character(character_id: uuid.UUID, session: DbSession) -> CharacterResponse:
    row = await get_character(session, character_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    return to_response(*row)


@router.patch("/characters/{character_id}", response_model=CharacterResponse)
async def admin_update_character(
    character_id: uuid.UUID,
    payload: CharacterUpdate,
    session: DbSession,
) -> CharacterResponse:
    row = await get_character(session, character_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    point, character = row
    values = payload.model_dump(exclude_unset=True)
    new_status = values.pop("status", None)
    if new_status is not None:
        point.status = new_status
    new_character = values.get("character")
    if new_character is not None:
        point.title = new_character
        point.canonical_key = f"zh-char:{new_character}"
    for key, value in values.items():
        setattr(character, key, value)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Character already exists",
        ) from error
    await session.refresh(point)
    await session.refresh(character)
    return to_response(point, character)


@router.post("/characters/import", response_model=ImportReport)
async def admin_import_characters(payload: BulkCharacterImport, session: DbSession) -> ImportReport:
    result = await import_characters(session, payload.items)
    return ImportReport(**result.__dict__)


@router.post("/characters/import-starter", response_model=ImportReport)
async def admin_import_starter(session: DbSession) -> ImportReport:
    result = await import_characters(session, load_starter_dataset())
    if not result.errors:
        relation_result = await import_starter_relations(session)
        result.errors.extend(relation_result.errors)
    return ImportReport(**result.__dict__)


@router.post(
    "/knowledge-relations",
    response_model=KnowledgeRelationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_relation(
    payload: KnowledgeRelationCreate, session: DbSession
) -> KnowledgeRelation:
    if payload.source_id == payload.target_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A knowledge point cannot relate to itself",
        )
    if (
        await session.get(KnowledgePoint, payload.source_id) is None
        or await session.get(KnowledgePoint, payload.target_id) is None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge point not found"
        )
    relation = KnowledgeRelation(**payload.model_dump())
    session.add(relation)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Knowledge relation already exists",
        ) from error
    await session.refresh(relation)
    return relation


@router.get("/knowledge-relations", response_model=list[KnowledgeRelationResponse])
async def admin_list_relations(session: DbSession) -> list[KnowledgeRelation]:
    return list(
        await session.scalars(select(KnowledgeRelation).order_by(KnowledgeRelation.created_at))
    )
