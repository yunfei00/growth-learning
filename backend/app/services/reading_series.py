"""Deterministic 30-day serialized reading progression.

Series content is child-private, ordered, and independent from mastery scoring. A
StoryVersion is materialized only when an episode becomes the child's next
reading item, so existing reading/session infrastructure remains authoritative.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Child,
    ChineseCharacter,
    FamilyMember,
    KnowledgePoint,
    ReadingSession,
    ReadingStatus,
    Story,
    StoryGenerationRun,
    StoryGenerationStatus,
    StoryKnowledgePoint,
    StoryKnowledgeRole,
    StoryVersion,
)
from app.models.reading_series import StoryEpisode, StorySeries
from app.reading_content import EPISODES, SERIES_CONTENT_VERSION, SERIES_SLUG, SERIES_TITLE
from app.schemas.reading_series import ReadingSeriesEpisodeResponse, ReadingSeriesProgressResponse
from app.services.story_analysis import (
    ANALYZER_VERSION,
    COVERAGE_POLICY_VERSION,
    analyze_story_coverage,
)
from app.services.story_generation import build_mastery_snapshot

SERIES_PROVIDER = "curated_series"
SERIES_MODEL = "ahai-season-1"
SERIES_PROMPT_VERSION = "reading-series-v1"
SERIES_THEME = "serialized_reading"


async def _author_user_id(session: AsyncSession, child_id: uuid.UUID) -> uuid.UUID:
    child = await session.get(Child, child_id)
    if child is None:
        raise LookupError("Child not found")
    user_id = await session.scalar(
        select(FamilyMember.user_id)
        .where(FamilyMember.family_id == child.family_id)
        .order_by(FamilyMember.created_at, FamilyMember.id)
        .limit(1)
    )
    if user_id is None:
        raise RuntimeError("Reading series requires at least one family member")
    return user_id


async def ensure_first_month_series(session: AsyncSession, child_id: uuid.UUID) -> StorySeries:
    """Create/update the deterministic first-month pack for one child."""

    series = await session.scalar(
        select(StorySeries).where(
            StorySeries.child_id == child_id,
            StorySeries.slug == SERIES_SLUG,
        )
    )
    if series is None:
        series = StorySeries(
            child_id=child_id,
            created_by_user_id=await _author_user_id(session, child_id),
            slug=SERIES_SLUG,
            title=SERIES_TITLE,
            season_number=1,
            total_episodes=len(EPISODES),
            content_version=SERIES_CONTENT_VERSION,
        )
        session.add(series)
        await session.flush()
    else:
        series.title = SERIES_TITLE
        series.total_episodes = len(EPISODES)
        series.content_version = SERIES_CONTENT_VERSION

    existing = {
        item.episode_number: item
        for item in (
            await session.scalars(
                select(StoryEpisode).where(StoryEpisode.series_id == series.id)
            )
        ).all()
    }
    for payload in EPISODES:
        number = int(payload["number"])
        episode = existing.get(number)
        if episode is None:
            session.add(
                StoryEpisode(
                    series_id=series.id,
                    episode_number=number,
                    chapter_title=str(payload["chapter"]),
                    title=str(payload["title"]),
                    paragraphs=list(payload["paragraphs"]),
                    focus_characters=list(payload["focus"]),
                )
            )
        elif episode.story_version_id is None:
            episode.chapter_title = str(payload["chapter"])
            episode.title = str(payload["title"])
            episode.paragraphs = list(payload["paragraphs"])
            episode.focus_characters = list(payload["focus"])
    await session.flush()
    return series


def _snapshot_payload(snapshot) -> dict[str, object]:
    return {
        "snapshot_at": snapshot.at.isoformat(),
        "catalog_size": snapshot.catalog_size,
        "mastery_algorithm_version": "v1",
        "strong_known": [
            {
                "knowledge_point_id": str(item.knowledge_point_id),
                "character": item.character,
                "mastery_level": item.mastery_level,
            }
            for item in snapshot.characters
            if item.character in snapshot.strong
        ],
        "usable_recognizing": [
            {
                "knowledge_point_id": str(item.knowledge_point_id),
                "character": item.character,
                "mastery_level": item.mastery_level,
            }
            for item in snapshot.characters
            if item.character in snapshot.recognizing
        ],
        "source": SERIES_PROVIDER,
    }


async def _materialize_episode(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    series: StorySeries,
    episode: StoryEpisode,
    now: datetime | None = None,
) -> StoryVersion:
    if episode.story_version_id is not None:
        version = await session.get(StoryVersion, episode.story_version_id)
        if version is not None:
            return version

    now = now or datetime.now(UTC)
    snapshot = await build_mastery_snapshot(session, child_id, now=now)
    focus = set(episode.focus_characters)
    analysis = analyze_story_coverage(
        title=episode.title,
        paragraphs=episode.paragraphs,
        strong_known=set(snapshot.strong),
        usable_recognizing=set(snapshot.recognizing),
        targets=focus,
    )
    if analysis.total_han_occurrences == 0:
        raise RuntimeError("Serialized episode must contain Han text")

    catalog_rows = list(
        (
            await session.execute(
                select(KnowledgePoint.id, ChineseCharacter.character)
                .join(ChineseCharacter)
                .where(ChineseCharacter.character.in_(set(analysis.occurrences)))
            )
        ).all()
    )
    target_ids = [str(point_id) for point_id, char in catalog_rows if char in focus]

    story = Story(
        child_id=child_id,
        created_by_user_id=series.created_by_user_id,
        theme=SERIES_THEME,
        custom_theme=series.title,
    )
    session.add(story)
    await session.flush()

    run = StoryGenerationRun(
        child_id=child_id,
        requested_by_user_id=series.created_by_user_id,
        story_id=story.id,
        status=StoryGenerationStatus.SUCCEEDED,
        difficulty="beginner",
        theme=SERIES_THEME,
        target_knowledge_point_ids=target_ids,
        provider=SERIES_PROVIDER,
        model=SERIES_MODEL,
        prompt_version=SERIES_PROMPT_VERSION,
        attempt_count=0,
        latency_ms=0,
        completed_at=now,
    )
    session.add(run)
    await session.flush()

    version = StoryVersion(
        story_id=story.id,
        generation_run_id=run.id,
        version_number=1,
        title=f"第{episode.episode_number}天｜{episode.title}",
        paragraphs=episode.paragraphs,
        summary=f"{series.title} · {episode.chapter_title}",
        theme=SERIES_THEME,
        custom_theme=series.title,
        difficulty="beginner",
        requested_known_coverage=0.0,
        actual_strong_known_coverage=analysis.strong_known_coverage,
        actual_usable_known_coverage=analysis.usable_known_coverage,
        actual_target_coverage=analysis.target_coverage,
        actual_unexpected_coverage=analysis.unexpected_coverage,
        unique_known_coverage=analysis.unique_known_coverage,
        total_han_occurrences=analysis.total_han_occurrences,
        unique_han_count=analysis.unique_han_count,
        unexpected_characters=list(analysis.unexpected_characters),
        target_characters=list(episode.focus_characters),
        mastery_snapshot=_snapshot_payload(snapshot),
        snapshot_at=snapshot.at,
        coverage_policy_version=COVERAGE_POLICY_VERSION,
        analyzer_version=ANALYZER_VERSION,
        prompt_version=SERIES_PROMPT_VERSION,
        provider=SERIES_PROVIDER,
        model=SERIES_MODEL,
    )
    session.add(version)
    await session.flush()

    snapshot_by_char = {item.character: item for item in snapshot.characters}
    for point_id, char in catalog_rows:
        if char in focus:
            role = StoryKnowledgeRole.TARGET
        elif char in snapshot.strong:
            role = StoryKnowledgeRole.STRONG_KNOWN
        elif char in snapshot.recognizing:
            role = StoryKnowledgeRole.USABLE_RECOGNIZING
        else:
            role = StoryKnowledgeRole.UNEXPECTED
        session.add(
            StoryKnowledgePoint(
                story_version_id=version.id,
                knowledge_point_id=point_id,
                role=role,
                occurrence_count=analysis.occurrence_counts[char],
                mastery_level_at_generation=(
                    snapshot_by_char[char].mastery_level if char in snapshot_by_char else None
                ),
            )
        )

    run.story_version_id = version.id
    episode.story_version_id = version.id
    await session.flush()
    return version


async def _completed_story_versions(
    session: AsyncSession, child_id: uuid.UUID
) -> set[uuid.UUID]:
    return set(
        (
            await session.scalars(
                select(ReadingSession.story_version_id).where(
                    ReadingSession.child_id == child_id,
                    ReadingSession.status == ReadingStatus.COMPLETED,
                )
            )
        ).all()
    )


async def next_series_story_version(
    session: AsyncSession, child_id: uuid.UUID
) -> tuple[StorySeries, StoryEpisode, StoryVersion] | None:
    """Return/materialize exactly the first unfinished episode in sequence."""

    series = await ensure_first_month_series(session, child_id)
    episodes = list(
        (
            await session.scalars(
                select(StoryEpisode)
                .where(StoryEpisode.series_id == series.id)
                .order_by(StoryEpisode.episode_number)
            )
        ).all()
    )
    completed = await _completed_story_versions(session, child_id)
    for episode in episodes:
        if episode.story_version_id is not None and episode.story_version_id in completed:
            continue
        version = await _materialize_episode(
            session,
            child_id=child_id,
            series=series,
            episode=episode,
        )
        return series, episode, version
    return None


async def episode_for_story_version(
    session: AsyncSession, story_version_id: uuid.UUID
) -> tuple[StorySeries, StoryEpisode] | None:
    return (
        await session.execute(
            select(StorySeries, StoryEpisode)
            .join(StoryEpisode, StoryEpisode.series_id == StorySeries.id)
            .where(StoryEpisode.story_version_id == story_version_id)
        )
    ).one_or_none()


async def reading_series_progress(
    session: AsyncSession, child_id: uuid.UUID
) -> ReadingSeriesProgressResponse:
    series = await ensure_first_month_series(session, child_id)
    episodes = list(
        (
            await session.scalars(
                select(StoryEpisode)
                .where(StoryEpisode.series_id == series.id)
                .order_by(StoryEpisode.episode_number)
            )
        ).all()
    )
    materialized_ids = [
        item.story_version_id for item in episodes if item.story_version_id is not None
    ]
    readings = {
        row[0]: row[1]
        for row in (
            await session.execute(
                select(ReadingSession.story_version_id, ReadingSession.status).where(
                    ReadingSession.child_id == child_id,
                    ReadingSession.story_version_id.in_(materialized_ids),
                )
            )
        ).all()
    }
    completed = 0
    current: StoryEpisode | None = None
    response_episodes: list[ReadingSeriesEpisodeResponse] = []
    for episode in episodes:
        reading_status = (
            readings.get(episode.story_version_id) if episode.story_version_id else None
        )
        if reading_status == ReadingStatus.COMPLETED:
            status = "completed"
            completed += 1
        elif reading_status == ReadingStatus.IN_PROGRESS:
            status = "in_progress"
            current = current or episode
        elif current is None:
            status = "current"
            current = episode
        else:
            status = "upcoming"
        response_episodes.append(
            ReadingSeriesEpisodeResponse(
                episode_number=episode.episode_number,
                chapter_title=episode.chapter_title,
                title=episode.title,
                status=status,
                story_version_id=episode.story_version_id,
            )
        )

    return ReadingSeriesProgressResponse(
        series_id=series.id,
        slug=series.slug,
        title=series.title,
        season_number=series.season_number,
        total_episodes=series.total_episodes,
        completed_episodes=completed,
        progress_percent=round(completed / series.total_episodes * 100, 1),
        current_episode_number=current.episode_number if current else None,
        current_episode_title=current.title if current else None,
        current_chapter_title=current.chapter_title if current else None,
        current_story_version_id=current.story_version_id if current else None,
        episodes=response_episodes,
    )
