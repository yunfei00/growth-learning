"""Canonical character catalog persistence and idempotent import."""

import json
import math
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChineseCharacter,
    KnowledgePoint,
    KnowledgeRelation,
    KnowledgeStatus,
    KnowledgeType,
)
from app.schemas.knowledge import CharacterCreate, CharacterPage, CharacterResponse

STARTER_DATASET = Path(__file__).resolve().parents[2] / "data" / "chinese_characters_v1.json"


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
