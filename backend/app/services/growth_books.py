"""Immutable, memory-oriented Growth Book editions."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ExperimentMediaAsset,
    ExperimentSession,
    GrowthBook,
    GrowthBookVersion,
    GrowthEvent,
    GrowthMediaAsset,
    ReadingSession,
)
from app.schemas.growth import GrowthBookCreate, GrowthBookSummary, GrowthBookVersionResponse

BOOK_POLICY_VERSION = "growth-book-v1"


async def create_growth_book_version(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    payload: GrowthBookCreate,
) -> GrowthBookVersion:
    event_ids = list(dict.fromkeys(payload.selected_event_ids))
    if event_ids:
        valid_events = set(
            (
                await session.scalars(
                    select(GrowthEvent.id).where(
                        GrowthEvent.child_id == child_id,
                        GrowthEvent.id.in_(event_ids),
                        GrowthEvent.archived_at.is_(None),
                    )
                )
            ).all()
        )
        if valid_events != set(event_ids):
            raise LookupError("One or more selected growth events are unavailable")

    validated_media: list[dict[str, str]] = []
    for reference in payload.selected_media:
        kind = reference.get("kind")
        raw_id = reference.get("id")
        try:
            media_id = uuid.UUID(raw_id or "")
        except ValueError as error:
            raise ValueError("Selected media reference is invalid") from error
        if kind == "growth":
            exists = await session.scalar(
                select(GrowthMediaAsset.id).where(
                    GrowthMediaAsset.id == media_id, GrowthMediaAsset.child_id == child_id
                )
            )
        elif kind == "science":
            exists = await session.scalar(
                select(ExperimentMediaAsset.id).where(
                    ExperimentMediaAsset.id == media_id,
                    ExperimentMediaAsset.child_id == child_id,
                )
            )
        else:
            raise ValueError("Selected media kind must be growth or science")
        if not exists:
            raise LookupError("Selected media is unavailable")
        validated_media.append({"kind": kind, "id": str(media_id)})

    book = await session.scalar(
        select(GrowthBook).where(
            GrowthBook.child_id == child_id,
            GrowthBook.edition_type == payload.edition_type,
            GrowthBook.edition_key == payload.edition_key,
        )
    )
    if book is None:
        book = GrowthBook(
            child_id=child_id,
            edition_type=payload.edition_type,
            edition_key=payload.edition_key,
            created_by_user_id=actor_user_id,
        )
        session.add(book)
        await session.flush()
    version_number = (
        int(
            await session.scalar(
                select(func.max(GrowthBookVersion.version_number)).where(
                    GrowthBookVersion.growth_book_id == book.id
                )
            )
            or 0
        )
        + 1
    )

    year = (
        int(payload.edition_key)
        if payload.edition_type == "yearly" and payload.edition_key.isdigit()
        else None
    )
    reading_query = (
        select(func.count())
        .select_from(ReadingSession)
        .where(ReadingSession.child_id == child_id, ReadingSession.status == "completed")
    )
    science_query = (
        select(func.count())
        .select_from(ExperimentSession)
        .where(ExperimentSession.child_id == child_id, ExperimentSession.status == "completed")
    )
    if year:
        reading_query = reading_query.where(
            func.extract("year", ReadingSession.completed_at) == year
        )
        science_query = science_query.where(
            func.extract("year", ExperimentSession.completed_at) == year
        )
    event_rows = (
        list(
            (
                await session.scalars(
                    select(GrowthEvent)
                    .where(GrowthEvent.id.in_(event_ids))
                    .order_by(GrowthEvent.occurred_at)
                )
            ).all()
        )
        if event_ids
        else []
    )
    snapshot: dict[str, object] = {
        "policy_version": BOOK_POLICY_VERSION,
        "edition_type": payload.edition_type,
        "edition_key": payload.edition_key,
        "events": [
            {
                "id": str(event.id),
                "occurred_at": event.occurred_at.isoformat(),
                "title": event.title,
                "body": event.body,
                "category": event.category,
                "source_entity_type": event.source_entity_type,
                "source_entity_id": str(event.source_entity_id) if event.source_entity_id else None,
            }
            for event in event_rows
        ],
        "facts": {
            "stories_completed": int(await session.scalar(reading_query) or 0),
            "science_experiments_completed": int(await session.scalar(science_query) or 0),
        },
        "score": None,
    }
    now = datetime.now(UTC)
    version = GrowthBookVersion(
        growth_book_id=book.id,
        version_number=version_number,
        title=payload.title,
        selected_event_ids=[str(item) for item in event_ids],
        selected_media=validated_media,
        snapshot=snapshot,
        parent_message=payload.parent_message,
        message_author_user_id=actor_user_id if payload.parent_message else None,
        message_recorded_at=now if payload.parent_message else None,
    )
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return version


async def growth_book_response(
    session: AsyncSession, version: GrowthBookVersion
) -> GrowthBookVersionResponse:
    book = await session.get(GrowthBook, version.growth_book_id)
    if book is None:
        raise LookupError("Growth book not found")
    return GrowthBookVersionResponse(
        id=version.id,
        growth_book_id=book.id,
        version_number=version.version_number,
        edition_type=book.edition_type,
        edition_key=book.edition_key,
        title=version.title,
        selected_event_ids=[uuid.UUID(item) for item in version.selected_event_ids],
        selected_media=version.selected_media,
        snapshot=version.snapshot,
        parent_message=version.parent_message,
        message_author_user_id=version.message_author_user_id,
        message_recorded_at=version.message_recorded_at,
        created_at=version.created_at,
    )


async def list_growth_books(session: AsyncSession, child_id: uuid.UUID) -> list[GrowthBookSummary]:
    books = list(
        (
            await session.scalars(
                select(GrowthBook)
                .where(GrowthBook.child_id == child_id)
                .order_by(GrowthBook.created_at.desc())
            )
        ).all()
    )
    result: list[GrowthBookSummary] = []
    for book in books:
        version = await session.scalar(
            select(GrowthBookVersion)
            .where(GrowthBookVersion.growth_book_id == book.id)
            .order_by(GrowthBookVersion.version_number.desc())
            .limit(1)
        )
        if version:
            result.append(
                GrowthBookSummary(
                    id=book.id,
                    edition_type=book.edition_type,
                    edition_key=book.edition_key,
                    latest_version=version.version_number,
                    title=version.title,
                    created_at=version.created_at,
                )
            )
    return result
