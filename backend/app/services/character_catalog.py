"""Canonical character catalog persistence and idempotent import."""

import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityKnowledgePoint,
    ActivityType,
    CatalogRelease,
    CharacterCatalogEntry,
    ChineseCharacter,
    Course,
    CourseSourceType,
    CourseStatus,
    CourseSubject,
    CourseUnit,
    KnowledgePoint,
    KnowledgePointRole,
    KnowledgeRelation,
    KnowledgeStatus,
    KnowledgeType,
    LearningActivity,
)
from app.schemas.knowledge import CharacterCreate, CharacterPage, CharacterResponse

STARTER_DATASET = Path(__file__).resolve().parents[2] / "data" / "chinese_characters_v1.json"
EXPANDED_DATASET = Path(__file__).resolve().parents[2] / "data" / "chinese_characters_v2.json"


def to_response(point: KnowledgePoint, character: ChineseCharacter) -> CharacterResponse:
    return CharacterResponse(
        id=point.id,
        character=character.character,
        pinyin=character.pinyin,
        stroke_count=character.stroke_count,
        radical=character.radical,
        frequency_rank=character.frequency_rank,
        difficulty_level=character.difficulty_level,
        simple_meaning=character.simple_meaning,
        example_sentence=character.example_sentence,
        parent_tip=character.parent_tip,
        common_words=character.common_words,
        tags=character.tags,
        is_enabled=character.is_enabled,
        status=point.status,
        source_type=point.source_type,
        source_reference=point.source_reference,
        created_at=point.created_at,
        updated_at=max(point.updated_at, character.updated_at),
    )


async def get_character(
    session: AsyncSession, character_id: uuid.UUID, *, enabled_only: bool = False
) -> tuple[KnowledgePoint, ChineseCharacter] | None:
    query = (
        select(KnowledgePoint, ChineseCharacter)
        .join(ChineseCharacter, ChineseCharacter.knowledge_point_id == KnowledgePoint.id)
        .where(KnowledgePoint.id == character_id)
    )
    if enabled_only:
        query = query.where(
            ChineseCharacter.is_enabled.is_(True),
            KnowledgePoint.status == KnowledgeStatus.ACTIVE,
        )
    return (await session.execute(query)).one_or_none()


async def list_characters(
    session: AsyncSession,
    *,
    search: str | None,
    enabled: bool | None,
    page: int,
    page_size: int,
    public_only: bool = False,
) -> CharacterPage:
    conditions = []
    if search:
        search_pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                ChineseCharacter.character.ilike(search_pattern),
                ChineseCharacter.pinyin.ilike(search_pattern),
            )
        )
    if enabled is not None:
        conditions.append(ChineseCharacter.is_enabled.is_(enabled))
    if public_only:
        conditions.extend(
            [
                ChineseCharacter.is_enabled.is_(True),
                KnowledgePoint.status == KnowledgeStatus.ACTIVE,
            ]
        )

    base = select(KnowledgePoint, ChineseCharacter).join(
        ChineseCharacter, ChineseCharacter.knowledge_point_id == KnowledgePoint.id
    )
    count_query = (
        select(func.count())
        .select_from(ChineseCharacter)
        .join(KnowledgePoint, KnowledgePoint.id == ChineseCharacter.knowledge_point_id)
    )
    if conditions:
        base = base.where(*conditions)
        count_query = count_query.where(*conditions)
    total = int(await session.scalar(count_query) or 0)
    rows = (
        await session.execute(
            base.order_by(ChineseCharacter.created_at, ChineseCharacter.character)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return CharacterPage(
        items=[to_response(point, character) for point, character in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


async def create_character(
    session: AsyncSession, payload: CharacterCreate
) -> tuple[KnowledgePoint, ChineseCharacter]:
    point = KnowledgePoint(
        subject=CourseSubject.CHINESE,
        type=KnowledgeType.CHINESE_CHARACTER,
        status=KnowledgeStatus.ACTIVE,
        title=payload.character,
        canonical_key=f"zh-char:{payload.character}",
        source_type=payload.source_type,
        source_reference=payload.source_reference,
    )
    session.add(point)
    await session.flush()
    values = payload.model_dump(exclude={"source_type", "source_reference"})
    character = ChineseCharacter(knowledge_point_id=point.id, **values)
    session.add(character)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise
    await session.refresh(point)
    await session.refresh(character)
    return point, character


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class CatalogImportResult(ImportResult):
    preserved: int = 0
    catalog_version: str = ""
    catalog_size: int = 0
    course_created: bool = False


async def import_characters(session: AsyncSession, items: list[CharacterCreate]) -> ImportResult:
    result = ImportResult()
    for index, payload in enumerate(items, start=1):
        try:
            row = (
                await session.execute(
                    select(KnowledgePoint, ChineseCharacter)
                    .join(ChineseCharacter)
                    .where(ChineseCharacter.character == payload.character)
                )
            ).one_or_none()
            if row is None:
                point = KnowledgePoint(
                    subject=CourseSubject.CHINESE,
                    type=KnowledgeType.CHINESE_CHARACTER,
                    status=KnowledgeStatus.ACTIVE,
                    title=payload.character,
                    canonical_key=f"zh-char:{payload.character}",
                    source_type=payload.source_type,
                    source_reference=payload.source_reference,
                )
                session.add(point)
                await session.flush()
                session.add(
                    ChineseCharacter(
                        knowledge_point_id=point.id,
                        **payload.model_dump(exclude={"source_type", "source_reference"}),
                    )
                )
                result.created += 1
                continue

            point, character = row
            desired = payload.model_dump(exclude={"source_type", "source_reference"})
            changed = point.status != KnowledgeStatus.ACTIVE
            for key, value in desired.items():
                if getattr(character, key) != value:
                    setattr(character, key, value)
                    changed = True
            for key in ("source_type", "source_reference"):
                value = getattr(payload, key)
                if getattr(point, key) != value:
                    setattr(point, key, value)
                    changed = True
            point.status = KnowledgeStatus.ACTIVE
            if changed:
                result.updated += 1
            else:
                result.skipped += 1
        except Exception as error:
            result.errors.append(f"Item {index} ({payload.character}): {type(error).__name__}")
    if result.errors:
        await session.rollback()
        return result
    await session.commit()
    return result


def load_starter_dataset() -> list[CharacterCreate]:
    payload = json.loads(STARTER_DATASET.read_text(encoding="utf-8"))
    if payload.get("version") != "1.0":
        raise ValueError("Unsupported starter dataset version")
    return [
        CharacterCreate.model_validate(
            {
                **item,
                "source_type": "project_starter",
                "source_reference": "chinese_characters_v1",
            }
        )
        for item in payload["items"]
    ]


def load_expanded_dataset() -> tuple[dict, list[CharacterCreate]]:
    payload = json.loads(EXPANDED_DATASET.read_text(encoding="utf-8"))
    if payload.get("version") != "2.0" or not payload.get("catalog_version"):
        raise ValueError("Unsupported expanded catalog version")
    items = [CharacterCreate.model_validate(item) for item in payload["items"]]
    if len({item.character for item in items}) != len(items):
        raise ValueError("Expanded catalog contains duplicate characters")
    return payload, items


async def _seed_system_course(
    session: AsyncSession, release: CatalogRelease, point_ids: list[uuid.UUID]
) -> bool:
    course = await session.scalar(
        select(Course).where(Course.system_key == "system-chinese-path-v1")
    )
    if course is not None:
        return False
    course = Course(
        subject=CourseSubject.CHINESE,
        title="系统汉字学习路径",
        description=(
            "Growth Learning 项目内部学习路径，按当前 canonical 字库组织；"
            "不是官方教育标准或教材字表。"
        ),
        source_type=CourseSourceType.SYSTEM,
        status=CourseStatus.ENABLED,
        version=1,
        system_key="system-chinese-path-v1",
        recommended_age_min=3,
        recommended_age_max=10,
        reference_metadata={"catalog_version": release.catalog_version},
    )
    session.add(course)
    await session.flush()
    stages = [
        ("起步 100", "先接触项目路径中的前 100 个常用字。", 0, 100),
        ("基础 300", "继续扩展到累计 300 个字。", 100, 300),
        ("进阶 500", "继续扩展到累计 500 个字。", 300, 500),
        ("扩展 1000+", "在当前版本字库内持续扩展。", 500, len(point_ids)),
    ]
    for unit_order, (title, description, start, end) in enumerate(stages):
        unit = CourseUnit(
            course_id=course.id,
            title=title,
            description=description,
            order_index=unit_order,
            status=CourseStatus.ENABLED,
        )
        session.add(unit)
        await session.flush()
        for offset in range(start, end, 10):
            activity = LearningActivity(
                course_unit_id=unit.id,
                activity_type=ActivityType.CHARACTER_LEARNING,
                title=f"识字 {offset + 1}–{min(offset + 10, end)}",
                instructions="按顺序接触新字；复习积压时今日计划可能暂停新字。",
                order_index=(offset - start) // 10,
                status=CourseStatus.ENABLED,
                content_metadata={"catalog_version": release.catalog_version},
            )
            session.add(activity)
            await session.flush()
            for position, point_id in enumerate(point_ids[offset : min(offset + 10, end)]):
                session.add(
                    ActivityKnowledgePoint(
                        activity_id=activity.id,
                        knowledge_point_id=point_id,
                        role=KnowledgePointRole.PRIMARY,
                        order_index=position,
                    )
                )
    return True


async def import_expanded_catalog(session: AsyncSession) -> CatalogImportResult:
    """Upsert the catalog without replacing canonical knowledge-point IDs."""

    payload, items = load_expanded_dataset()
    existing_ids = dict(
        (
            await session.execute(
                select(ChineseCharacter.character, ChineseCharacter.knowledge_point_id).where(
                    ChineseCharacter.character.in_([item.character for item in items])
                )
            )
        ).all()
    )
    imported = await import_characters(session, items)
    result = CatalogImportResult(
        created=imported.created,
        updated=imported.updated,
        skipped=imported.skipped,
        errors=imported.errors,
        preserved=len(existing_ids),
        catalog_version=payload["catalog_version"],
        catalog_size=len(items),
    )
    if result.errors:
        return result

    current_ids = dict(
        (
            await session.execute(
                select(ChineseCharacter.character, ChineseCharacter.knowledge_point_id).where(
                    ChineseCharacter.character.in_([item.character for item in items])
                )
            )
        ).all()
    )
    changed_ids = [
        character
        for character, point_id in existing_ids.items()
        if current_ids.get(character) != point_id
    ]
    if changed_ids:
        await session.rollback()
        result.errors.append("Canonical knowledge-point IDs changed during import")
        return result

    provenance = payload["provenance"]
    release = await session.scalar(
        select(CatalogRelease).where(CatalogRelease.catalog_version == payload["catalog_version"])
    )
    if release is None:
        release = CatalogRelease(
            catalog_version=payload["catalog_version"],
            source_type=provenance["source_type"],
            source_name=provenance["source_name"],
            source_reference=provenance["source_reference"],
            license=provenance["license"],
            imported_at=datetime.now(UTC),
            item_count=len(items),
            is_current=True,
            metadata_json={
                "notice": payload["notice"],
                "selection_method": provenance["selection_method"],
            },
        )
        session.add(release)
        await session.flush()
    else:
        release.item_count = len(items)
        release.is_current = True
    other_releases = list(
        (await session.scalars(select(CatalogRelease).where(CatalogRelease.id != release.id))).all()
    )
    for other in other_releases:
        other.is_current = False

    existing_entries = set(
        (
            await session.scalars(
                select(CharacterCatalogEntry.knowledge_point_id).where(
                    CharacterCatalogEntry.catalog_release_id == release.id
                )
            )
        ).all()
    )
    point_ids: list[uuid.UUID] = []
    for position, item in enumerate(items):
        point_id = current_ids[item.character]
        point_ids.append(point_id)
        if point_id not in existing_entries:
            session.add(
                CharacterCatalogEntry(
                    catalog_release_id=release.id,
                    knowledge_point_id=point_id,
                    order_index=position,
                    source_reference=item.source_reference,
                )
            )
    result.course_created = await _seed_system_course(session, release, point_ids)
    await session.commit()
    return result


async def import_starter_relations(session: AsyncSession) -> ImportResult:
    """Idempotently import the small relation sample bundled with the starter catalog."""
    payload = json.loads(STARTER_DATASET.read_text(encoding="utf-8"))
    result = ImportResult()
    character_ids = dict(
        (
            await session.execute(
                select(ChineseCharacter.character, ChineseCharacter.knowledge_point_id)
            )
        ).all()
    )
    for index, item in enumerate(payload.get("relations", []), start=1):
        source_id = character_ids.get(item["source"])
        target_id = character_ids.get(item["target"])
        if source_id is None or target_id is None:
            result.errors.append(f"Relation {index}: referenced character is missing")
            continue
        exists = await session.scalar(
            select(KnowledgeRelation.id).where(
                KnowledgeRelation.source_id == source_id,
                KnowledgeRelation.target_id == target_id,
                KnowledgeRelation.relation_type == item["relation_type"],
            )
        )
        if exists is not None:
            result.skipped += 1
            continue
        session.add(
            KnowledgeRelation(
                source_id=source_id,
                target_id=target_id,
                relation_type=item["relation_type"],
            )
        )
        result.created += 1
    if result.errors:
        await session.rollback()
        return result
    await session.commit()
    return result
