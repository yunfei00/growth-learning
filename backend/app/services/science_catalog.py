"""Science experiment catalog, immutable versions, and idempotent starter import."""

import json
import math
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChineseCharacter,
    ExperimentKnowledgePoint,
    ExperimentMaterial,
    ExperimentMaterialRequirement,
    KnowledgePoint,
    ScienceExperiment,
    ScienceExperimentVersion,
)
from app.schemas.science import (
    KnowledgePointLinkResponse,
    MaterialCreate,
    MaterialRequirementInput,
    MaterialRequirementResponse,
    MaterialResponse,
    ScienceExperimentCreate,
    ScienceExperimentPage,
    ScienceExperimentResponse,
    ScienceExperimentUpdate,
)

DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "science_experiments_v1.json"


@dataclass
class ScienceImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    materials_created: int = 0
    errors: list[str] = field(default_factory=list)


def load_starter_science_dataset() -> dict[str, object]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


async def get_or_create_material(
    session: AsyncSession, payload: MaterialCreate
) -> tuple[ExperimentMaterial, bool]:
    material = await session.scalar(
        select(ExperimentMaterial).where(
            or_(
                ExperimentMaterial.canonical_key == payload.canonical_key,
                ExperimentMaterial.name == payload.name,
            )
        )
    )
    if material is None:
        material = ExperimentMaterial(**payload.model_dump())
        session.add(material)
        await session.flush()
        return material, True
    for key, value in payload.model_dump().items():
        setattr(material, key, value)
    await session.flush()
    return material, False


async def _replace_requirements(
    session: AsyncSession,
    experiment_id: uuid.UUID,
    requirements: list[MaterialRequirementInput],
) -> int:
    await session.execute(
        delete(ExperimentMaterialRequirement).where(
            ExperimentMaterialRequirement.experiment_id == experiment_id
        )
    )
    created_materials = 0
    seen: set[uuid.UUID] = set()
    for position, item in enumerate(requirements):
        if item.material is not None:
            material, created = await get_or_create_material(session, item.material)
            created_materials += int(created)
        else:
            material = await session.get(ExperimentMaterial, item.material_id)
            if material is None:
                raise ValueError("Material not found")
        if material.id in seen:
            raise ValueError("An experiment cannot require the same material twice")
        seen.add(material.id)
        session.add(
            ExperimentMaterialRequirement(
                experiment_id=experiment_id,
                material_id=material.id,
                quantity_text=item.quantity_text,
                is_required=item.is_required,
                substitution_notes=item.substitution_notes,
                position=item.position if item.position else position,
            )
        )
    await session.flush()
    return created_materials


async def _replace_knowledge_links(
    session: AsyncSession, experiment_id: uuid.UUID, point_ids: list[uuid.UUID]
) -> None:
    unique_ids = list(dict.fromkeys(point_ids))
    if unique_ids:
        count = int(
            await session.scalar(
                select(func.count())
                .select_from(KnowledgePoint)
                .where(KnowledgePoint.id.in_(unique_ids))
            )
            or 0
        )
        if count != len(unique_ids):
            raise ValueError("Knowledge point not found")
    await session.execute(
        delete(ExperimentKnowledgePoint).where(
            ExperimentKnowledgePoint.experiment_id == experiment_id
        )
    )
    session.add_all(
        ExperimentKnowledgePoint(
            experiment_id=experiment_id,
            knowledge_point_id=point_id,
            exposure_enabled=True,
        )
        for point_id in unique_ids
    )
    await session.flush()


async def experiment_snapshot(
    session: AsyncSession, experiment: ScienceExperiment
) -> dict[str, object]:
    requirement_rows = list(
        (
            await session.execute(
                select(ExperimentMaterialRequirement, ExperimentMaterial)
                .join(
                    ExperimentMaterial,
                    ExperimentMaterial.id == ExperimentMaterialRequirement.material_id,
                )
                .where(ExperimentMaterialRequirement.experiment_id == experiment.id)
                .order_by(ExperimentMaterialRequirement.position, ExperimentMaterial.name)
            )
        ).all()
    )
    point_rows = list(
        (
            await session.execute(
                select(
                    ExperimentKnowledgePoint.knowledge_point_id,
                    KnowledgePoint.title,
                    ChineseCharacter.character,
                )
                .select_from(ExperimentKnowledgePoint)
                .join(
                    KnowledgePoint,
                    KnowledgePoint.id == ExperimentKnowledgePoint.knowledge_point_id,
                )
                .outerjoin(
                    ChineseCharacter,
                    ChineseCharacter.knowledge_point_id == KnowledgePoint.id,
                )
                .where(ExperimentKnowledgePoint.experiment_id == experiment.id)
                .order_by(KnowledgePoint.title)
            )
        ).all()
    )
    return {
        "experiment_id": str(experiment.id),
        "canonical_key": experiment.canonical_key,
        "title": experiment.title,
        "description": experiment.description,
        "age_min": experiment.age_min,
        "age_max": experiment.age_max,
        "difficulty": experiment.difficulty,
        "estimated_duration_minutes": experiment.estimated_duration_minutes,
        "guiding_question": experiment.guiding_question,
        "expected_phenomenon": experiment.expected_phenomenon,
        "child_friendly_explanation": experiment.child_friendly_explanation,
        "parent_scientific_explanation": experiment.parent_scientific_explanation,
        "safety_notes": list(experiment.safety_notes),
        "common_failure_reasons": list(experiment.common_failure_reasons),
        "follow_up_questions": list(experiment.follow_up_questions),
        "likely_child_questions": list(experiment.likely_child_questions),
        "steps": list(experiment.steps),
        "requirements": [
            {
                "material_id": str(material.id),
                "canonical_key": material.canonical_key,
                "name": material.name,
                "quantity_text": requirement.quantity_text,
                "is_required": requirement.is_required,
                "substitution_notes": requirement.substitution_notes,
                "safety_note": material.safety_note,
                "position": requirement.position,
            }
            for requirement, material in requirement_rows
        ],
        "related_knowledge_points": [
            {
                "knowledge_point_id": str(point_id),
                "title": title,
                "character": character,
            }
            for point_id, title, character in point_rows
        ],
        "snapshot_schema_version": "science-template-v1",
    }


async def create_experiment_version(
    session: AsyncSession,
    experiment: ScienceExperiment,
    *,
    actor_user_id: uuid.UUID | None,
) -> ScienceExperimentVersion:
    snapshot = await experiment_snapshot(session, experiment)
    latest = await session.scalar(
        select(ScienceExperimentVersion)
        .where(ScienceExperimentVersion.experiment_id == experiment.id)
        .order_by(ScienceExperimentVersion.version_number.desc())
        .limit(1)
    )
    if latest is not None and latest.snapshot == snapshot:
        return latest
    number = 1 if latest is None else latest.version_number + 1
    experiment.content_version = number
    version = ScienceExperimentVersion(
        experiment_id=experiment.id,
        version_number=number,
        snapshot=snapshot,
        created_by_user_id=actor_user_id,
    )
    session.add(version)
    await session.flush()
    return version


async def create_science_experiment(
    session: AsyncSession,
    payload: ScienceExperimentCreate,
    *,
    actor_user_id: uuid.UUID | None,
) -> tuple[ScienceExperiment, int]:
    values = payload.model_dump(exclude={"requirements", "related_knowledge_point_ids"})
    experiment = ScienceExperiment(**values, created_by_user_id=actor_user_id)
    session.add(experiment)
    await session.flush()
    material_count = await _replace_requirements(session, experiment.id, payload.requirements)
    await _replace_knowledge_links(session, experiment.id, payload.related_knowledge_point_ids)
    await create_experiment_version(session, experiment, actor_user_id=actor_user_id)
    await session.commit()
    await session.refresh(experiment)
    return experiment, material_count


async def update_science_experiment(
    session: AsyncSession,
    experiment: ScienceExperiment,
    payload: ScienceExperimentUpdate,
    *,
    actor_user_id: uuid.UUID | None,
) -> int:
    values = payload.model_dump(
        exclude_unset=True, exclude={"requirements", "related_knowledge_point_ids"}
    )
    for key, value in values.items():
        setattr(experiment, key, value)
    age_min = experiment.age_min
    age_max = experiment.age_max
    if age_max is not None and age_max < age_min:
        raise ValueError("age_max must be greater than or equal to age_min")
    material_count = 0
    if payload.requirements is not None:
        material_count = await _replace_requirements(session, experiment.id, payload.requirements)
    if payload.related_knowledge_point_ids is not None:
        await _replace_knowledge_links(session, experiment.id, payload.related_knowledge_point_ids)
    await session.flush()
    await create_experiment_version(session, experiment, actor_user_id=actor_user_id)
    await session.commit()
    await session.refresh(experiment)
    return material_count


async def get_science_experiment(
    session: AsyncSession, experiment_id: uuid.UUID
) -> ScienceExperiment | None:
    return await session.get(ScienceExperiment, experiment_id)


def _material_response(material: ExperimentMaterial) -> MaterialResponse:
    return MaterialResponse.model_validate(material)


async def science_experiment_response(
    session: AsyncSession, experiment: ScienceExperiment
) -> ScienceExperimentResponse:
    requirements = list(
        (
            await session.execute(
                select(ExperimentMaterialRequirement, ExperimentMaterial)
                .join(ExperimentMaterial)
                .where(ExperimentMaterialRequirement.experiment_id == experiment.id)
                .order_by(ExperimentMaterialRequirement.position, ExperimentMaterial.name)
            )
        ).all()
    )
    points = list(
        (
            await session.execute(
                select(
                    ExperimentKnowledgePoint,
                    KnowledgePoint,
                    ChineseCharacter.character,
                )
                .select_from(ExperimentKnowledgePoint)
                .join(
                    KnowledgePoint,
                    KnowledgePoint.id == ExperimentKnowledgePoint.knowledge_point_id,
                )
                .outerjoin(
                    ChineseCharacter,
                    ChineseCharacter.knowledge_point_id == KnowledgePoint.id,
                )
                .where(ExperimentKnowledgePoint.experiment_id == experiment.id)
                .order_by(KnowledgePoint.title)
            )
        ).all()
    )
    return ScienceExperimentResponse(
        id=experiment.id,
        canonical_key=experiment.canonical_key,
        title=experiment.title,
        description=experiment.description,
        age_min=experiment.age_min,
        age_max=experiment.age_max,
        difficulty=experiment.difficulty,
        estimated_duration_minutes=experiment.estimated_duration_minutes,
        guiding_question=experiment.guiding_question,
        expected_phenomenon=experiment.expected_phenomenon,
        child_friendly_explanation=experiment.child_friendly_explanation,
        parent_scientific_explanation=experiment.parent_scientific_explanation,
        safety_notes=list(experiment.safety_notes),
        common_failure_reasons=list(experiment.common_failure_reasons),
        follow_up_questions=list(experiment.follow_up_questions),
        likely_child_questions=list(experiment.likely_child_questions),
        steps=list(experiment.steps),
        status=experiment.status,
        source_type=experiment.source_type,
        content_version=experiment.content_version,
        requirements=[
            MaterialRequirementResponse(
                id=requirement.id,
                material=_material_response(material),
                quantity_text=requirement.quantity_text,
                is_required=requirement.is_required,
                substitution_notes=requirement.substitution_notes,
                position=requirement.position,
            )
            for requirement, material in requirements
        ],
        related_knowledge_points=[
            KnowledgePointLinkResponse(
                knowledge_point_id=link.knowledge_point_id,
                title=point.title,
                character=character,
                exposure_enabled=link.exposure_enabled,
            )
            for link, point, character in points
        ],
        created_at=experiment.created_at,
        updated_at=experiment.updated_at,
    )


async def list_science_experiments(
    session: AsyncSession,
    *,
    search: str | None = None,
    status: str | None = None,
    difficulty: str | None = None,
    page: int = 1,
    page_size: int = 20,
    system_only: bool = False,
) -> ScienceExperimentPage:
    conditions = []
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                ScienceExperiment.title.ilike(pattern), ScienceExperiment.description.ilike(pattern)
            )
        )
    if status:
        conditions.append(ScienceExperiment.status == status)
    if difficulty:
        conditions.append(ScienceExperiment.difficulty == difficulty)
    if system_only:
        conditions.append(ScienceExperiment.owner_family_id.is_(None))
    total = int(
        await session.scalar(select(func.count()).select_from(ScienceExperiment).where(*conditions))
        or 0
    )
    experiments = list(
        (
            await session.scalars(
                select(ScienceExperiment)
                .where(*conditions)
                .order_by(
                    ScienceExperiment.status, ScienceExperiment.age_min, ScienceExperiment.title
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return ScienceExperimentPage(
        items=[await science_experiment_response(session, item) for item in experiments],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


def _starter_payload(
    item: dict[str, object], material_map: dict[str, MaterialCreate], point_ids: list[uuid.UUID]
) -> ScienceExperimentCreate:
    requirements: list[MaterialRequirementInput] = []
    for position, requirement in enumerate(item.get("materials", [])):
        material_key = requirement["key"]
        requirements.append(
            MaterialRequirementInput(
                material=material_map[material_key],
                quantity_text=requirement.get("quantity"),
                is_required=requirement.get("required", True),
                substitution_notes=requirement.get("substitution"),
                position=position,
            )
        )
    return ScienceExperimentCreate(
        canonical_key=item["canonical_key"],
        title=item["title"],
        description=item["description"],
        age_min=item["age_min"],
        age_max=item.get("age_max"),
        difficulty=item["difficulty"],
        estimated_duration_minutes=item["estimated_duration_minutes"],
        guiding_question=item["guiding_question"],
        expected_phenomenon=item["expected_phenomenon"],
        child_friendly_explanation=item["child_friendly_explanation"],
        parent_scientific_explanation=item["parent_scientific_explanation"],
        safety_notes=item["safety_notes"],
        common_failure_reasons=item["common_failure_reasons"],
        follow_up_questions=item["follow_up_questions"],
        likely_child_questions=item["likely_child_questions"],
        steps=item["steps"],
        status="enabled",
        source_type="system",
        requirements=requirements,
        related_knowledge_point_ids=point_ids,
    )


async def import_starter_science_experiments(session: AsyncSession) -> ScienceImportResult:
    dataset = load_starter_science_dataset()
    material_map = {
        item["canonical_key"]: MaterialCreate.model_validate(item) for item in dataset["materials"]
    }
    result = ScienceImportResult()
    for item in dataset["experiments"]:
        try:
            characters = list(dict.fromkeys(item.get("related_characters", [])))
            point_ids: list[uuid.UUID] = []
            if characters:
                point_ids = list(
                    (
                        await session.scalars(
                            select(ChineseCharacter.knowledge_point_id).where(
                                ChineseCharacter.character.in_(characters)
                            )
                        )
                    ).all()
                )
            payload = _starter_payload(item, material_map, point_ids)
            experiment = await session.scalar(
                select(ScienceExperiment).where(
                    ScienceExperiment.canonical_key == payload.canonical_key
                )
            )
            if experiment is None:
                _, created_materials = await create_science_experiment(
                    session, payload, actor_user_id=None
                )
                result.created += 1
                result.materials_created += created_materials
                continue
            prior_version = experiment.content_version
            update_payload = ScienceExperimentUpdate(
                **payload.model_dump(exclude={"canonical_key", "source_type"})
            )
            created_materials = await update_science_experiment(
                session, experiment, update_payload, actor_user_id=None
            )
            result.materials_created += created_materials
            if experiment.content_version > prior_version:
                result.updated += 1
            else:
                result.skipped += 1
        except Exception as error:  # noqa: BLE001 - report item errors without losing earlier imports
            await session.rollback()
            result.errors.append(f"{item.get('canonical_key', 'unknown')}: {error}")
    return result
