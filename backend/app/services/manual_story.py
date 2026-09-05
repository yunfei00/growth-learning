"""Parent-authored assisted stories without a literacy admission gate.

Manual stories reuse the immutable Story/StoryVersion model and the existing
reading evidence pipeline. Coverage is measured for guidance only; it never
blocks a parent from saving a story for assisted reading.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Child,
    ChineseCharacter,
    KnowledgePoint,
    Story,
    StoryGenerationRun,
    StoryGenerationStatus,
    StoryKnowledgePoint,
    StoryKnowledgeRole,
    StoryVersion,
)
from app.schemas.story import ParentStoryCreateRequest
from app.services.daily_reading import attach_story_to_today
from app.services.review_planning import get_or_create_daily_plan
from app.services.story_analysis import ANALYZER_VERSION, COVERAGE_POLICY_VERSION, analyze_story_coverage
from app.services.story_generation import MasterySnapshot, build_mastery_snapshot

MANUAL_STORY_PROMPT_VERSION = "parent-story-v1"
MANUAL_STORY_PROVIDER = "parent_manual"
MANUAL_STORY_MODEL = "parent-authored"
MANUAL_STORY_THEME = "parent_authored"
MAX_TTS_PARAGRAPH_CHARS = 220
MAX_STORY_PARAGRAPHS = 24


def _split_long_line(line: str) -> list[str]:
    if len(line) <= MAX_TTS_PARAGRAPH_CHARS:
        return [line]
    sentences = [part.strip() for part in re.findall(r"[^。！？!?；;]+[。！？!?；;]?", line) if part.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > MAX_TTS_PARAGRAPH_CHARS:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                sentence[index : index + MAX_TTS_PARAGRAPH_CHARS]
                for index in range(0, len(sentence), MAX_TTS_PARAGRAPH_CHARS)
            )
            continue
        if current and len(current) + len(sentence) > MAX_TTS_PARAGRAPH_CHARS:
            chunks.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        chunks.append(current)
    return chunks


def split_story_paragraphs(text: str) -> list[str]:
    """Normalize pasted text and bound each paragraph for reliable TTS calls."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("故事内容不能为空")
    paragraphs: list[str] = []
    for line in (line.strip() for line in normalized.split("\n") if line.strip()):
        paragraphs.extend(_split_long_line(line))
    if not paragraphs:
        raise ValueError("故事内容不能为空")
    if len(paragraphs) > MAX_STORY_PARAGRAPHS:
        raise ValueError("故事分段后超过 24 段，请先精简内容")
    return paragraphs


def _snapshot_payload(snapshot: MasterySnapshot) -> dict[str, object]:
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
        "targets": [],
        "source": MANUAL_STORY_PROVIDER,
    }


async def create_parent_story(
    session: AsyncSession,
    *,
    child: Child,
    created_by_user_id: uuid.UUID,
    payload: ParentStoryCreateRequest,
    now: datetime | None = None,
) -> tuple[StoryGenerationRun, StoryVersion]:
    """Persist one private assisted-reading story and its coverage snapshot."""

    now = now or datetime.now(UTC)
    title = payload.title.strip()
    paragraphs = split_story_paragraphs(payload.content)
    snapshot = await build_mastery_snapshot(session, child.id, now=now)
    analysis = analyze_story_coverage(
        title=title,
        paragraphs=paragraphs,
        strong_known=set(snapshot.strong),
        usable_recognizing=set(snapshot.recognizing),
        targets=set(),
    )
    if analysis.total_han_occurrences == 0:
        raise ValueError("故事至少需要包含一个汉字")

    story = Story(
        child_id=child.id,
        created_by_user_id=created_by_user_id,
        theme=MANUAL_STORY_THEME,
        custom_theme=None,
    )
    session.add(story)
    await session.flush()

    run = StoryGenerationRun(
        child_id=child.id,
        requested_by_user_id=created_by_user_id,
        story_id=story.id,
        status=StoryGenerationStatus.SUCCEEDED,
        difficulty="beginner",
        theme=MANUAL_STORY_THEME,
        target_knowledge_point_ids=[],
        provider=MANUAL_STORY_PROVIDER,
        model=MANUAL_STORY_MODEL,
        prompt_version=MANUAL_STORY_PROMPT_VERSION,
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
        title=title,
        paragraphs=paragraphs,
        summary=None,
        theme=MANUAL_STORY_THEME,
        custom_theme=None,
        difficulty="beginner",
        requested_known_coverage=0.0,
        actual_strong_known_coverage=analysis.strong_known_coverage,
        actual_usable_known_coverage=analysis.usable_known_coverage,
        actual_target_coverage=0.0,
        actual_unexpected_coverage=analysis.unexpected_coverage,
        unique_known_coverage=analysis.unique_known_coverage,
        total_han_occurrences=analysis.total_han_occurrences,
        unique_han_count=analysis.unique_han_count,
        unexpected_characters=list(analysis.unexpected_characters),
        target_characters=[],
        mastery_snapshot=_snapshot_payload(snapshot),
        snapshot_at=snapshot.at,
        coverage_policy_version=COVERAGE_POLICY_VERSION,
        analyzer_version=ANALYZER_VERSION,
        prompt_version=MANUAL_STORY_PROMPT_VERSION,
        provider=MANUAL_STORY_PROVIDER,
        model=MANUAL_STORY_MODEL,
    )
    session.add(version)
    await session.flush()

    catalog_rows = list(
        (
            await session.execute(
                select(KnowledgePoint.id, ChineseCharacter.character)
                .join(ChineseCharacter)
                .where(ChineseCharacter.character.in_(set(analysis.occurrences)))
            )
        ).all()
    )
    snapshot_by_char = {item.character: item for item in snapshot.characters}
    for point_id, char in catalog_rows:
        if char in snapshot.strong:
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
    await get_or_create_daily_plan(session, child.id)
    await attach_story_to_today(session, child.id, version.id)
    await session.commit()
    await session.refresh(version)
    return run, version
