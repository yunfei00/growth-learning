"""Deterministic science recommendations and append-oriented experiment sessions."""

import copy
import math
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentItem,
    Child,
    ExperimentEvidence,
    ExperimentKnowledgePoint,
    ExperimentMaterial,
    ExperimentMaterialRequirement,
    ExperimentMediaAsset,
    ExperimentSession,
    ExperimentSessionStatus,
    ExperimentStep,
    FamilyMaterial,
    LearningActivityType,
    LearningRecord,
    LearningSession,
    ScienceDifficulty,
    ScienceExperiment,
    ScienceExperimentStatus,
    ScienceExperimentVersion,
    SessionStatus,
    User,
)
from app.schemas.science import (
    ExperimentCompleteRequest,
    ExperimentEvidenceBatch,
    ExperimentEvidenceResponse,
    ExperimentEvidenceUpdate,
    ExperimentGrowthCardResponse,
    ExperimentMediaResponse,
    ExperimentRecommendationResponse,
    ExperimentSessionCreate,
    ExperimentSessionPage,
    ExperimentSessionResponse,
    ExperimentSessionUpdate,
    FamilyMaterialBatchUpdate,
    FamilyMaterialResponse,
    MaterialResponse,
)
from app.services.science_catalog import science_experiment_response

CAPABILITY_TAGS = {
    "observation",
    "questioning",
    "prediction",
    "hands_on",
    "causal_reasoning",
    "expression",
}
DIFFICULTY_RANK = {
    ScienceDifficulty.INTRO: 0,
    ScienceDifficulty.EXPLORE: 1,
    ScienceDifficulty.ADVANCED: 2,
}


def child_age_years(birth_date: date, today: date | None = None) -> int:
    today = today or datetime.now(UTC).date()
    return max(
        0,
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day)),
    )


def _is_age_appropriate(experiment: ScienceExperiment, age: int) -> bool:
    return experiment.age_min <= age and (experiment.age_max is None or age <= experiment.age_max)


async def list_family_material_inventory(
    session: AsyncSession, family_id: uuid.UUID
) -> list[FamilyMaterialResponse]:
    rows = list(
        (
            await session.execute(
                select(ExperimentMaterial, FamilyMaterial)
                .outerjoin(
                    FamilyMaterial,
                    (FamilyMaterial.material_id == ExperimentMaterial.id)
                    & (FamilyMaterial.family_id == family_id),
                )
                .where(ExperimentMaterial.is_active.is_(True))
                .order_by(ExperimentMaterial.category, ExperimentMaterial.name)
            )
        ).all()
    )
    return [
        FamilyMaterialResponse(
            material=MaterialResponse.model_validate(material),
            is_owned=inventory.is_owned if inventory else False,
            quantity_text=inventory.quantity_text if inventory else None,
            note=inventory.note if inventory else None,
            updated_at=inventory.updated_at if inventory else None,
        )
        for material, inventory in rows
    ]


async def update_family_material_inventory(
    session: AsyncSession,
    *,
    family_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    payload: FamilyMaterialBatchUpdate,
) -> list[FamilyMaterialResponse]:
    material_ids = list(dict.fromkeys(item.material_id for item in payload.items))
    existing_count = int(
        await session.scalar(
            select(func.count())
            .select_from(ExperimentMaterial)
            .where(ExperimentMaterial.id.in_(material_ids), ExperimentMaterial.is_active.is_(True))
        )
        or 0
    )
    if existing_count != len(material_ids):
        raise LookupError("Material not found")
    for item in payload.items:
        inventory = await session.scalar(
            select(FamilyMaterial).where(
                FamilyMaterial.family_id == family_id,
                FamilyMaterial.material_id == item.material_id,
            )
        )
        if inventory is None:
            inventory = FamilyMaterial(
                family_id=family_id,
                material_id=item.material_id,
                updated_by_user_id=actor_user_id,
            )
            session.add(inventory)
        inventory.is_owned = item.is_owned
        inventory.quantity_text = item.quantity_text
        inventory.note = item.note
        inventory.updated_by_user_id = actor_user_id
    await session.commit()
    return await list_family_material_inventory(session, family_id)


async def _material_match(
    session: AsyncSession,
    experiment_id: uuid.UUID,
    owned_ids: set[uuid.UUID],
) -> tuple[list[str], list[str], list[str]]:
    rows = list(
        (
            await session.execute(
                select(ExperimentMaterialRequirement, ExperimentMaterial)
                .join(ExperimentMaterial)
                .where(ExperimentMaterialRequirement.experiment_id == experiment_id)
                .order_by(ExperimentMaterialRequirement.position)
            )
        ).all()
    )
    owned = [
        material.name
        for requirement, material in rows
        if requirement.is_required and material.id in owned_ids
    ]
    missing = [
        material.name
        for requirement, material in rows
        if requirement.is_required and material.id not in owned_ids
    ]
    substitutions = [
        f"{material.name}：{requirement.substitution_notes}"
        for requirement, material in rows
        if requirement.substitution_notes
    ]
    return owned, missing, substitutions


async def recommend_science_experiments(
    session: AsyncSession,
    child: Child,
    *,
    limit: int = 6,
    today: date | None = None,
) -> list[ExperimentRecommendationResponse]:
    today = today or datetime.now(UTC).date()
    age = child_age_years(child.birth_date, today)
    experiments = list(
        (
            await session.scalars(
                select(ScienceExperiment).where(
                    ScienceExperiment.status == ScienceExperimentStatus.ENABLED,
                    (ScienceExperiment.owner_family_id.is_(None))
                    | (ScienceExperiment.owner_family_id == child.family_id),
                )
            )
        ).all()
    )
    owned_ids = set(
        (
            await session.scalars(
                select(FamilyMaterial.material_id).where(
                    FamilyMaterial.family_id == child.family_id,
                    FamilyMaterial.is_owned.is_(True),
                )
            )
        ).all()
    )
    recent_cutoff = datetime.combine(today - timedelta(days=60), datetime.min.time(), tzinfo=UTC)
    recent_rows = list(
        (
            await session.execute(
                select(ExperimentSession.experiment_id, func.max(ExperimentSession.completed_at))
                .where(
                    ExperimentSession.child_id == child.id,
                    ExperimentSession.status == ExperimentSessionStatus.COMPLETED,
                    ExperimentSession.completed_at >= recent_cutoff,
                )
                .group_by(ExperimentSession.experiment_id)
            )
        ).all()
    )
    recent_ids = {row[0] for row in recent_rows}
    completed_difficulties = list(
        (
            await session.scalars(
                select(ScienceExperiment.difficulty)
                .join(
                    ExperimentSession,
                    ExperimentSession.experiment_id == ScienceExperiment.id,
                )
                .where(
                    ExperimentSession.child_id == child.id,
                    ExperimentSession.status == ExperimentSessionStatus.COMPLETED,
                )
            )
        ).all()
    )
    if completed_difficulties:
        target_rank = min(2, max(DIFFICULTY_RANK[value] for value in completed_difficulties) + 1)
    else:
        target_rank = 0 if age <= 4 else 1 if age <= 7 else 2

    scored: list[tuple[tuple[object, ...], ScienceExperiment, list[str], list[str], list[str]]] = []
    for experiment in experiments:
        owned, missing, substitutions = await _material_match(session, experiment.id, owned_ids)
        age_ok = _is_age_appropriate(experiment, age)
        recent = experiment.id in recent_ids
        score = (
            not age_ok,
            recent,
            bool(missing),
            len(missing),
            abs(DIFFICULTY_RANK[experiment.difficulty] - target_rank),
            experiment.title,
        )
        scored.append((score, experiment, owned, missing, substitutions))

    responses: list[ExperimentRecommendationResponse] = []
    for _, experiment, owned, missing, substitutions in sorted(scored, key=lambda item: item[0])[
        :limit
    ]:
        reasons: list[str] = []
        if _is_age_appropriate(experiment, age):
            reasons.append("适合当前年龄段")
        if not missing:
            reasons.append("家中现有材料即可完成")
        elif owned:
            reasons.append("家里已有大部分材料")
        if experiment.id not in recent_ids:
            reasons.append("最近没有做过同一实验")
        if abs(DIFFICULTY_RANK[experiment.difficulty] - target_rank) <= 1:
            reasons.append("符合当前探索进阶节奏")
        responses.append(
            ExperimentRecommendationResponse(
                experiment=await science_experiment_response(session, experiment),
                ready_at_home=not missing,
                owned_required_materials=owned,
                missing_required_materials=missing,
                optional_substitutions=substitutions,
                reasons=reasons,
                recently_completed=experiment.id in recent_ids,
            )
        )
    return responses


async def _latest_experiment_version(
    session: AsyncSession, experiment_id: uuid.UUID
) -> ScienceExperimentVersion | None:
    return await session.scalar(
        select(ScienceExperimentVersion)
        .where(ScienceExperimentVersion.experiment_id == experiment_id)
        .order_by(ScienceExperimentVersion.version_number.desc())
        .limit(1)
    )


async def _active_experiment_session(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    experiment_id: uuid.UUID,
) -> ExperimentSession | None:
    return await session.scalar(
        select(ExperimentSession)
        .where(
            ExperimentSession.child_id == child_id,
            ExperimentSession.experiment_id == experiment_id,
            ExperimentSession.status.in_(["planned", "in_progress"]),
        )
        .order_by(ExperimentSession.created_at)
        .limit(1)
    )


async def create_or_resume_experiment_session(
    session: AsyncSession,
    *,
    child: Child,
    actor_user_id: uuid.UUID,
    payload: ExperimentSessionCreate,
    now: datetime | None = None,
) -> ExperimentSession:
    now = now or datetime.now(UTC)
    if payload.request_key:
        prior = await session.scalar(
            select(ExperimentSession).where(
                ExperimentSession.child_id == child.id,
                ExperimentSession.request_key == payload.request_key,
            )
        )
        if prior is not None:
            return prior
    experiment = await session.scalar(
        select(ScienceExperiment).where(
            ScienceExperiment.id == payload.experiment_id,
            ScienceExperiment.status == ScienceExperimentStatus.ENABLED,
            (ScienceExperiment.owner_family_id.is_(None))
            | (ScienceExperiment.owner_family_id == child.family_id),
        )
    )
    if experiment is None:
        raise LookupError("Science experiment not found")
    active = await _active_experiment_session(
        session,
        child_id=child.id,
        experiment_id=experiment.id,
    )
    if active is not None:
        return active
    version = await _latest_experiment_version(session, experiment.id)
    if version is None:
        raise RuntimeError("Science experiment has no immutable version")
    status = (
        ExperimentSessionStatus.IN_PROGRESS
        if payload.start_immediately
        else ExperimentSessionStatus.PLANNED
    )
    experiment_session = ExperimentSession(
        child_id=child.id,
        experiment_id=experiment.id,
        experiment_version_id=version.id,
        experiment_snapshot=copy.deepcopy(version.snapshot),
        accompanying_user_id=actor_user_id,
        request_key=payload.request_key,
        status=status,
        current_step=ExperimentStep.QUESTION,
        local_date=now.date(),
        timezone=payload.timezone,
        started_at=now if payload.start_immediately else None,
    )
    session.add(experiment_session)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        active = await _active_experiment_session(
            session,
            child_id=child.id,
            experiment_id=experiment.id,
        )
        if active is not None:
            return active
        raise
    await session.refresh(experiment_session)
    return experiment_session


async def update_experiment_session(
    session: AsyncSession,
    experiment_session: ExperimentSession,
    payload: ExperimentSessionUpdate,
    *,
    can_manage_parent_note: bool,
    now: datetime | None = None,
) -> ExperimentSession:
    now = now or datetime.now(UTC)
    if experiment_session.status == ExperimentSessionStatus.ABANDONED:
        raise ValueError("Abandoned experiment sessions are immutable")
    if experiment_session.status == ExperimentSessionStatus.COMPLETED and (
        payload.action is not None or payload.current_step is not None
    ):
        raise ValueError("A completed experiment must remain completed")
    if "parent_note" in payload.model_fields_set:
        if not can_manage_parent_note:
            raise PermissionError("Family administrator permission required for parent note")
        experiment_session.parent_note = payload.parent_note
    if payload.action == "start":
        if experiment_session.status == ExperimentSessionStatus.PLANNED:
            experiment_session.status = ExperimentSessionStatus.IN_PROGRESS
            experiment_session.started_at = now
    elif payload.action == "abandon":
        experiment_session.status = ExperimentSessionStatus.ABANDONED
        experiment_session.completed_at = now
    elif payload.current_step:
        experiment_session.current_step = payload.current_step
    await session.commit()
    await session.refresh(experiment_session)
    return experiment_session


async def append_experiment_evidence(
    session: AsyncSession,
    *,
    experiment_session: ExperimentSession,
    child_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    payload: ExperimentEvidenceBatch,
) -> list[ExperimentEvidence]:
    if experiment_session.status not in (
        ExperimentSessionStatus.IN_PROGRESS,
        ExperimentSessionStatus.COMPLETED,
    ):
        raise ValueError("Experiment session cannot accept evidence")
    added: list[ExperimentEvidence] = []
    for item in payload.items:
        if item.client_key:
            prior = await session.scalar(
                select(ExperimentEvidence).where(
                    ExperimentEvidence.experiment_session_id == experiment_session.id,
                    ExperimentEvidence.client_key == item.client_key,
                )
            )
            if prior is not None:
                added.append(prior)
                continue
        evidence = ExperimentEvidence(
            experiment_session_id=experiment_session.id,
            child_id=child_id,
            evidence_type=item.evidence_type,
            original_text=item.original_text,
            capability_tags=list(item.capability_tags),
            recorder_user_id=actor_user_id,
            client_key=item.client_key,
        )
        session.add(evidence)
        added.append(evidence)
    experiment_session.updated_at = datetime.now(UTC)
    await session.commit()
    for item in added:
        await session.refresh(item)
    return added


async def get_private_experiment_evidence(
    session: AsyncSession,
    *,
    experiment_session_id: uuid.UUID,
    evidence_id: uuid.UUID,
) -> ExperimentEvidence | None:
    return await session.scalar(
        select(ExperimentEvidence).where(
            ExperimentEvidence.id == evidence_id,
            ExperimentEvidence.experiment_session_id == experiment_session_id,
        )
    )


async def update_experiment_evidence(
    session: AsyncSession,
    *,
    experiment_session: ExperimentSession,
    evidence: ExperimentEvidence,
    payload: ExperimentEvidenceUpdate,
    now: datetime | None = None,
) -> ExperimentEvidence:
    if experiment_session.status not in (
        ExperimentSessionStatus.IN_PROGRESS,
        ExperimentSessionStatus.COMPLETED,
    ):
        raise ValueError("Experiment session evidence is immutable")
    if payload.original_text is not None:
        evidence.original_text = payload.original_text
    if payload.capability_tags is not None:
        evidence.capability_tags = list(payload.capability_tags)
    experiment_session.updated_at = now or datetime.now(UTC)
    await session.commit()
    await session.refresh(evidence)
    return evidence


async def get_private_experiment_session(
    session: AsyncSession, child_id: uuid.UUID, experiment_session_id: uuid.UUID
) -> ExperimentSession | None:
    return await session.scalar(
        select(ExperimentSession).where(
            ExperimentSession.id == experiment_session_id,
            ExperimentSession.child_id == child_id,
        )
    )


def _media_response(child_id: uuid.UUID, asset: ExperimentMediaAsset) -> ExperimentMediaResponse:
    return ExperimentMediaResponse(
        id=asset.id,
        media_kind=asset.media_kind,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        original_filename=asset.original_filename,
        uploader_user_id=asset.uploader_user_id,
        created_at=asset.created_at,
        content_url=(
            f"/api/v1/children/{child_id}/experiment-sessions/"
            f"{asset.experiment_session_id}/media/{asset.id}/content"
        ),
    )


async def experiment_session_response(
    session: AsyncSession, experiment_session: ExperimentSession
) -> ExperimentSessionResponse:
    evidence = list(
        (
            await session.scalars(
                select(ExperimentEvidence)
                .where(ExperimentEvidence.experiment_session_id == experiment_session.id)
                .order_by(ExperimentEvidence.captured_at, ExperimentEvidence.id)
            )
        ).all()
    )
    media = list(
        (
            await session.scalars(
                select(ExperimentMediaAsset)
                .where(ExperimentMediaAsset.experiment_session_id == experiment_session.id)
                .order_by(ExperimentMediaAsset.created_at, ExperimentMediaAsset.id)
            )
        ).all()
    )
    exposure_count = 0
    if experiment_session.exposure_learning_session_id:
        exposure_count = int(
            await session.scalar(
                select(func.count())
                .select_from(LearningRecord)
                .where(LearningRecord.session_id == experiment_session.exposure_learning_session_id)
            )
            or 0
        )
    return ExperimentSessionResponse(
        id=experiment_session.id,
        child_id=experiment_session.child_id,
        experiment_id=experiment_session.experiment_id,
        experiment_version_id=experiment_session.experiment_version_id,
        experiment_snapshot=copy.deepcopy(experiment_session.experiment_snapshot),
        accompanying_user_id=experiment_session.accompanying_user_id,
        status=experiment_session.status,
        current_step=experiment_session.current_step,
        local_date=experiment_session.local_date,
        timezone=experiment_session.timezone,
        started_at=experiment_session.started_at,
        completed_at=experiment_session.completed_at,
        parent_note=experiment_session.parent_note,
        evidence=[ExperimentEvidenceResponse.model_validate(item) for item in evidence],
        media=[_media_response(experiment_session.child_id, item) for item in media],
        science_exposure_count=exposure_count,
        created_at=experiment_session.created_at,
        updated_at=experiment_session.updated_at,
    )


async def list_experiment_sessions(
    session: AsyncSession,
    child_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
) -> ExperimentSessionPage:
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(ExperimentSession)
            .where(ExperimentSession.child_id == child_id)
        )
        or 0
    )
    rows = list(
        (
            await session.scalars(
                select(ExperimentSession)
                .where(ExperimentSession.child_id == child_id)
                .order_by(ExperimentSession.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return ExperimentSessionPage(
        items=[await experiment_session_response(session, item) for item in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def complete_experiment_session(
    session: AsyncSession,
    experiment_session: ExperimentSession,
    *,
    actor_user_id: uuid.UUID,
    payload: ExperimentCompleteRequest,
    now: datetime | None = None,
) -> ExperimentSession:
    now = now or datetime.now(UTC)
    if experiment_session.status == ExperimentSessionStatus.COMPLETED:
        return experiment_session
    if experiment_session.status != ExperimentSessionStatus.IN_PROGRESS:
        raise ValueError("Only an in-progress experiment can be completed")
    if experiment_session.exposure_learning_session_id is None:
        point_ids = list(
            (
                await session.scalars(
                    select(ExperimentKnowledgePoint.knowledge_point_id).where(
                        ExperimentKnowledgePoint.experiment_id == experiment_session.experiment_id,
                        ExperimentKnowledgePoint.exposure_enabled.is_(True),
                    )
                )
            ).all()
        )
        exposure_session = LearningSession(
            child_id=experiment_session.child_id,
            actor_user_id=actor_user_id,
            status=SessionStatus.COMPLETED,
            source="science_experiment",
            started_at=experiment_session.started_at or now,
            completed_at=now,
        )
        session.add(exposure_session)
        await session.flush()
        for point_id in point_ids:
            session.add(
                LearningRecord(
                    session_id=exposure_session.id,
                    child_id=experiment_session.child_id,
                    knowledge_point_id=point_id,
                    actor_user_id=actor_user_id,
                    activity_type=LearningActivityType.SCIENCE_EXPERIMENT_EXPOSURE,
                    source="science_experiment",
                    learned_at=now,
                )
            )
        experiment_session.exposure_learning_session_id = exposure_session.id
        await session.flush()
        from app.services.mastery import recompute_child_knowledge_state
        from app.services.review_planning import recompute_review_schedule

        for point_id in point_ids:
            await recompute_child_knowledge_state(session, experiment_session.child_id, point_id)
            await recompute_review_schedule(session, experiment_session.child_id, point_id)
    experiment_session.status = ExperimentSessionStatus.COMPLETED
    experiment_session.current_step = ExperimentStep.COMPLETE
    experiment_session.completed_at = now
    if payload.parent_note is not None:
        experiment_session.parent_note = payload.parent_note
    await session.commit()
    await session.refresh(experiment_session)
    return experiment_session


async def experiment_growth_card(
    session: AsyncSession, experiment_session: ExperimentSession
) -> ExperimentGrowthCardResponse:
    if experiment_session.status != ExperimentSessionStatus.COMPLETED:
        raise ValueError("Growth card is available after experiment completion")
    response = await experiment_session_response(session, experiment_session)
    evidence_by_type: dict[str, list[str]] = {}
    capability_tags: list[str] = []
    for evidence in response.evidence:
        evidence_by_type.setdefault(evidence.evidence_type, []).append(evidence.original_text)
        capability_tags.extend(evidence.capability_tags)
    actor = await session.get(User, experiment_session.accompanying_user_id)
    snapshot = experiment_session.experiment_snapshot
    points = snapshot.get("related_knowledge_points", [])
    return ExperimentGrowthCardResponse(
        session_id=experiment_session.id,
        title=str(snapshot.get("title", "科学实验")),
        completed_at=experiment_session.completed_at,
        accompanying_user=actor.display_name if actor else "家庭陪伴者",
        prediction=evidence_by_type.get("prediction", []),
        observation=evidence_by_type.get("observation", []),
        child_original_words=evidence_by_type.get("child_original_words", []),
        child_summary=evidence_by_type.get("child_summary", []),
        questions_asked=evidence_by_type.get("question_asked", []),
        media=response.media,
        scientific_explanation=str(snapshot.get("child_friendly_explanation", "")),
        follow_up_questions=list(snapshot.get("follow_up_questions", [])),
        related_characters=[
            str(point["character"])
            for point in points
            if isinstance(point, dict) and point.get("character")
        ],
        capability_tags=list(dict.fromkeys(capability_tags)),
    )


async def assessment_count_for_child(session: AsyncSession, child_id: uuid.UUID) -> int:
    """Acceptance helper: experiment completion must not create recognition outcomes."""
    return int(
        await session.scalar(
            select(func.count())
            .select_from(AssessmentItem)
            .where(AssessmentItem.child_id == child_id)
        )
        or 0
    )
