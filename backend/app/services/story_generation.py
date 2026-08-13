"""Mastery snapshot, target selection, structured generation, and immutable persistence."""

import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ai.base import AICompletionRequest, AIMessage, AIProvider, AIProviderError
from app.models import (
    Child,
    ChildKnowledgeState,
    ChineseCharacter,
    KnowledgePoint,
    KnowledgeStatus,
    MasteryLevel,
    ReadingQuestion,
    Story,
    StoryDifficulty,
    StoryGenerationRun,
    StoryGenerationStatus,
    StoryKnowledgePoint,
    StoryKnowledgeRole,
    StoryVersion,
)
from app.schemas.story import (
    GeneratedStoryPayload,
    MasteryCharacterResponse,
    StoryGenerationContextResponse,
    StoryGenerationRequest,
)
from app.services.story_analysis import (
    ANALYZER_VERSION,
    COVERAGE_POLICY_VERSION,
    PROFILES,
    analyze_story_coverage,
    story_feasibility,
    validate_story_coverage,
)

PROMPT_VERSION = "story-prompt-v1"
CATALOG_LIMITATION = "当前故事约束基于系统 200 字 Starter Catalog，不代表完整儿童基础汉字体系。"
SAFE_THEMES: dict[str, str] = {
    "animals": "动物",
    "dinosaurs": "恐龙",
    "vehicles": "汽车",
    "space": "太空",
    "nature": "自然",
    "family_life": "家庭生活",
    "science": "科学探索",
}
UNSAFE_TERMS = {
    "色情",
    "性爱",
    "赌博",
    "毒品",
    "自杀",
    "自残",
    "谋杀",
    "虐待",
    "枪战",
    "成人内容",
}


class StoryGenerationError(RuntimeError):
    def __init__(self, message: str, *, category: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code


@dataclass(frozen=True)
class SnapshotCharacter:
    knowledge_point_id: uuid.UUID
    character: str
    mastery_level: str
    mastery_score: float
    is_priority: bool
    incorrect_count: int
    uncertain_count: int
    last_assessed_at: datetime | None


@dataclass(frozen=True)
class MasterySnapshot:
    at: datetime
    characters: tuple[SnapshotCharacter, ...]
    strong: frozenset[str]
    recognizing: frozenset[str]
    by_point_id: dict[uuid.UUID, SnapshotCharacter]
    catalog_size: int


def child_age_band(birth_date: date, today: date | None = None) -> str:
    today = today or datetime.now(UTC).date()
    years = (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )
    lower = max(3, min(11, years))
    return f"{lower}～{lower + 1}岁"


def validate_theme(theme: str, custom_theme: str | None) -> tuple[str, str | None]:
    if theme not in SAFE_THEMES:
        raise StoryGenerationError("请选择安全主题", category="unsafe_theme")
    custom = custom_theme.strip() if custom_theme else None
    if custom and any(term in custom.lower() for term in UNSAFE_TERMS):
        raise StoryGenerationError(
            "自定义主题不适合儿童故事，请更换主题", category="unsafe_custom_theme"
        )
    return theme, custom


async def build_mastery_snapshot(
    session: AsyncSession, child_id: uuid.UUID, *, now: datetime | None = None
) -> MasterySnapshot:
    rows = list(
        (
            await session.execute(
                select(ChildKnowledgeState, ChineseCharacter)
                .join(
                    ChineseCharacter,
                    ChineseCharacter.knowledge_point_id == ChildKnowledgeState.knowledge_point_id,
                )
                .join(KnowledgePoint, KnowledgePoint.id == ChildKnowledgeState.knowledge_point_id)
                .where(
                    ChildKnowledgeState.child_id == child_id,
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChineseCharacter.is_enabled.is_(True),
                )
            )
        ).all()
    )
    characters = tuple(
        SnapshotCharacter(
            knowledge_point_id=state.knowledge_point_id,
            character=character.character,
            mastery_level=state.mastery_level,
            mastery_score=state.mastery_score,
            is_priority=state.is_priority,
            incorrect_count=state.incorrect_count,
            uncertain_count=state.uncertain_count,
            last_assessed_at=state.last_assessed_at,
        )
        for state, character in rows
    )
    catalog_size = int(
        await session.scalar(
            select(func.count())
            .select_from(ChineseCharacter)
            .join(KnowledgePoint)
            .where(
                KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                ChineseCharacter.is_enabled.is_(True),
            )
        )
        or 0
    )
    return MasterySnapshot(
        at=now or datetime.now(UTC),
        characters=characters,
        strong=frozenset(
            item.character
            for item in characters
            if item.mastery_level in (MasteryLevel.PROFICIENT, MasteryLevel.STABLE)
        ),
        recognizing=frozenset(
            item.character for item in characters if item.mastery_level == MasteryLevel.RECOGNIZING
        ),
        by_point_id={item.knowledge_point_id: item for item in characters},
        catalog_size=catalog_size,
    )


def automatic_targets(snapshot: MasterySnapshot, limit: int = 3) -> list[SnapshotCharacter]:
    candidates = [
        item
        for item in snapshot.characters
        if item.mastery_level
        in (MasteryLevel.INTRODUCED, MasteryLevel.RECOGNIZING, MasteryLevel.PROFICIENT)
    ]

    def target_key(item: SnapshotCharacter) -> tuple[object, ...]:
        assessed = item.last_assessed_at or datetime.min.replace(tzinfo=UTC)
        return (
            not item.is_priority,
            -(item.incorrect_count + item.uncertain_count),
            item.mastery_score,
            -assessed.toordinal(),
            item.character,
        )

    return sorted(candidates, key=target_key)[:limit]


def recommended_difficulty(snapshot: MasterySnapshot) -> str | None:
    count = len(snapshot.strong)
    for difficulty in (
        StoryDifficulty.CHALLENGE,
        StoryDifficulty.NORMAL,
        StoryDifficulty.BEGINNER,
    ):
        if count >= PROFILES[difficulty].minimum_strong_known_characters:
            return difficulty
    return None


async def generation_context(
    session: AsyncSession,
    child: Child,
    *,
    provider_configured: bool,
    provider: str,
    model: str,
) -> StoryGenerationContextResponse:
    snapshot = await build_mastery_snapshot(session, child.id)
    recommendation = recommended_difficulty(snapshot)
    targets = automatic_targets(snapshot, 5)
    return StoryGenerationContextResponse(
        child_id=child.id,
        age_band=child_age_band(child.birth_date),
        provider_configured=provider_configured,
        provider=provider,
        model=model,
        recommended_difficulty=recommendation,
        strong_known_count=len(snapshot.strong),
        usable_recognizing_count=len(snapshot.recognizing),
        automatic_targets=[
            MasteryCharacterResponse(
                knowledge_point_id=item.knowledge_point_id,
                character=item.character,
                mastery_level=item.mastery_level,
                is_priority=item.is_priority,
            )
            for item in targets
        ],
        safe_themes=list(SAFE_THEMES),
        catalog_size=snapshot.catalog_size,
        catalog_limitation=CATALOG_LIMITATION,
        feasibility_message=(
            story_feasibility(StoryDifficulty.BEGINNER, len(snapshot.strong))
            if recommendation is None
            else None
        ),
    )


async def _resolve_targets(
    session: AsyncSession,
    snapshot: MasterySnapshot,
    requested_ids: list[uuid.UUID] | None,
) -> list[SnapshotCharacter]:
    if requested_ids is None:
        targets = automatic_targets(snapshot)
        if len(targets) < 2:
            raise StoryGenerationError(
                "当前没有足够的待巩固目标字，请先继续识字学习或测评。",
                category="insufficient_targets",
            )
        return targets
    rows = list(
        (
            await session.execute(
                select(KnowledgePoint.id, ChineseCharacter.character)
                .join(ChineseCharacter)
                .where(
                    KnowledgePoint.id.in_(requested_ids),
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChineseCharacter.is_enabled.is_(True),
                )
            )
        ).all()
    )
    if len(rows) != len(set(requested_ids)):
        raise StoryGenerationError("一个或多个目标字不可用", category="invalid_target")
    by_id = dict(rows)
    return [
        snapshot.by_point_id.get(point_id)
        or SnapshotCharacter(
            point_id, by_id[point_id], MasteryLevel.UNLEARNED, 0, False, 0, 0, None
        )
        for point_id in requested_ids
    ]


def _snapshot_payload(
    snapshot: MasterySnapshot, targets: list[SnapshotCharacter]
) -> dict[str, object]:
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
        "targets": [
            {
                "knowledge_point_id": str(item.knowledge_point_id),
                "character": item.character,
                "mastery_level": item.mastery_level,
            }
            for item in targets
        ],
    }


def _prompt(
    *,
    age_band: str,
    theme: str,
    custom_theme: str | None,
    difficulty: str,
    known: set[str],
    recognizing: set[str],
    targets: list[SnapshotCharacter],
    repair_reasons: tuple[str, ...] = (),
) -> AICompletionRequest:
    profile = PROFILES[difficulty]
    contract = {
        "task": "生成家长陪伴模式的简体中文儿童故事，不与孩子开放聊天",
        "age_band": age_band,
        "theme": SAFE_THEMES[theme],
        "custom_theme": custom_theme,
        "difficulty": difficulty,
        "coverage": {
            "known_target": profile.target_known,
            "known_allowed_range": [profile.min_known, profile.max_known],
            "target_allowed_range": [profile.min_target, profile.max_target],
            "unexpected_max": profile.max_unexpected,
        },
        "strong_known_characters": "".join(sorted(known)),
        "recognizing_usable_characters": "".join(sorted(recognizing)),
        "required_target_characters": [item.character for item in targets],
        "requirements": [
            "目标字必须在自然完整的情节中出现",
            "内容温暖、安全、适合年龄段，禁止成人、暴力、自伤、毒品和赌博内容",
            "避免不在已知字、可用字、目标字集合内的汉字",
            "故事正文至少达到指定汉字长度，语言自然，不能堆砌重复汉字",
            "生成2到3道简单选择题",
        ],
        "repair_reasons": list(repair_reasons),
        "json_schema": {
            "title": "string",
            "paragraphs": ["string"],
            "summary": "string or null",
            "questions": [
                {
                    "question": "string",
                    "options": ["string", "string", "string"],
                    "correct_option_index": 0,
                }
            ],
        },
    }
    return AICompletionRequest(
        messages=[
            AIMessage(
                role="system",
                content=(
                    "你是受控儿童阅读内容生成器。只返回严格 JSON，不返回 Markdown，"
                    "不返回思维过程，不索取或猜测儿童个人信息。"
                ),
            ),
            AIMessage(role="user", content=json.dumps(contract, ensure_ascii=False)),
        ],
        temperature=0.2,
        max_tokens=1400,
        json_response=True,
    )


def _content_is_safe(payload: GeneratedStoryPayload) -> bool:
    content = " ".join(
        [payload.title, *payload.paragraphs, *(q.question for q in payload.questions)]
    )
    return not any(term in content.lower() for term in UNSAFE_TERMS)


async def generate_story(
    session: AsyncSession,
    *,
    child: Child,
    requested_by_user_id: uuid.UUID,
    payload: StoryGenerationRequest,
    provider: AIProvider,
    provider_name: str,
    configured_model: str,
    max_attempts: int = 3,
    now: datetime | None = None,
) -> tuple[StoryGenerationRun, StoryVersion]:
    theme, custom_theme = validate_theme(payload.theme, payload.custom_theme)
    snapshot = await build_mastery_snapshot(session, child.id, now=now)
    feasibility = story_feasibility(payload.difficulty, len(snapshot.strong))
    if feasibility:
        raise StoryGenerationError(feasibility, category="insufficient_literacy")
    targets = await _resolve_targets(session, snapshot, payload.target_knowledge_point_ids)
    target_chars = {item.character for item in targets}
    strong = set(snapshot.strong) - target_chars
    recognizing = set(snapshot.recognizing) - target_chars

    if payload.request_key:
        prior = await session.scalar(
            select(StoryGenerationRun).where(
                StoryGenerationRun.request_key == payload.request_key,
                StoryGenerationRun.child_id == child.id,
            )
        )
        if prior and prior.status == StoryGenerationStatus.SUCCEEDED and prior.story_version_id:
            version = await session.get(StoryVersion, prior.story_version_id)
            if version is not None:
                return prior, version

    story: Story | None = None
    if payload.story_id:
        story = await session.scalar(
            select(Story).where(Story.id == payload.story_id, Story.child_id == child.id)
        )
        if story is None:
            raise StoryGenerationError("故事不存在", category="story_not_found", status_code=404)

    run = StoryGenerationRun(
        child_id=child.id,
        requested_by_user_id=requested_by_user_id,
        story_id=story.id if story else None,
        request_key=payload.request_key,
        difficulty=payload.difficulty,
        theme=theme,
        target_knowledge_point_ids=[str(item.knowledge_point_id) for item in targets],
        provider=provider_name,
        model=configured_model,
        prompt_version=PROMPT_VERSION,
    )
    session.add(run)
    await session.flush()
    started = time.perf_counter()
    last_reasons: tuple[str, ...] = ()
    last_response = None

    for attempt in range(1, min(max_attempts, 3) + 1):
        run.attempt_count = attempt
        try:
            response = await provider.complete(
                _prompt(
                    age_band=child_age_band(child.birth_date),
                    theme=theme,
                    custom_theme=custom_theme,
                    difficulty=payload.difficulty,
                    known=strong,
                    recognizing=recognizing,
                    targets=targets,
                    repair_reasons=last_reasons,
                )
            )
            last_response = response
            draft = GeneratedStoryPayload.model_validate_json(response.text)
        except ValidationError:
            last_reasons = ("structured_response_invalid",)
            continue
        except AIProviderError as exc:
            run.status = StoryGenerationStatus.FAILED
            run.failure_category = "provider_error"
            run.failure_message = "AI 服务暂时不可用，请稍后重试"
            run.completed_at = datetime.now(UTC)
            run.latency_ms = round((time.perf_counter() - started) * 1000)
            await session.commit()
            raise StoryGenerationError(
                "AI 服务暂时不可用，请稍后重试", category="provider_error", status_code=503
            ) from exc

        if not _content_is_safe(draft):
            last_reasons = ("content_safety_failed",)
            continue
        analysis = analyze_story_coverage(
            title=draft.title,
            paragraphs=draft.paragraphs,
            strong_known=strong,
            usable_recognizing=recognizing,
            targets=target_chars,
        )
        validation = validate_story_coverage(analysis, payload.difficulty, target_chars)
        if not validation.accepted:
            last_reasons = validation.reasons
            continue

        if story is None:
            story = Story(
                child_id=child.id,
                created_by_user_id=requested_by_user_id,
                theme=theme,
                custom_theme=custom_theme,
            )
            session.add(story)
            await session.flush()
            run.story_id = story.id
        version_number = (
            int(
                await session.scalar(
                    select(func.count())
                    .select_from(StoryVersion)
                    .where(StoryVersion.story_id == story.id)
                )
                or 0
            )
            + 1
        )
        version = StoryVersion(
            story_id=story.id,
            generation_run_id=run.id,
            version_number=version_number,
            title=draft.title,
            paragraphs=draft.paragraphs,
            summary=draft.summary,
            difficulty=payload.difficulty,
            requested_known_coverage=PROFILES[payload.difficulty].target_known,
            actual_strong_known_coverage=analysis.strong_known_coverage,
            actual_usable_known_coverage=analysis.usable_known_coverage,
            actual_target_coverage=analysis.target_coverage,
            actual_unexpected_coverage=analysis.unexpected_coverage,
            unique_known_coverage=analysis.unique_known_coverage,
            total_han_occurrences=analysis.total_han_occurrences,
            unique_han_count=analysis.unique_han_count,
            unexpected_characters=list(analysis.unexpected_characters),
            target_characters=[item.character for item in targets],
            mastery_snapshot=_snapshot_payload(snapshot, targets),
            snapshot_at=snapshot.at,
            coverage_policy_version=COVERAGE_POLICY_VERSION,
            analyzer_version=ANALYZER_VERSION,
            prompt_version=PROMPT_VERSION,
            provider=response.provider,
            model=response.model,
        )
        session.add(version)
        await session.flush()
        for position, question in enumerate(draft.questions):
            session.add(
                ReadingQuestion(
                    story_version_id=version.id,
                    position=position,
                    question=question.question,
                    options=question.options,
                    correct_option_index=question.correct_option_index,
                )
            )

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
            if char in target_chars:
                role = StoryKnowledgeRole.TARGET
            elif char in strong:
                role = StoryKnowledgeRole.STRONG_KNOWN
            elif char in recognizing:
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
        run.status = StoryGenerationStatus.SUCCEEDED
        run.provider = response.provider
        run.model = response.model
        run.latency_ms = round((time.perf_counter() - started) * 1000)
        run.input_tokens = response.input_tokens
        run.output_tokens = response.output_tokens
        run.completed_at = datetime.now(UTC)
        from app.services.daily_reading import attach_story_to_today

        await attach_story_to_today(session, child.id, version.id)
        await session.commit()
        return run, version

    run.status = StoryGenerationStatus.FAILED
    run.failure_category = "validation_failed"
    run.failure_message = ",".join(last_reasons)[:240]
    run.latency_ms = round((time.perf_counter() - started) * 1000)
    run.input_tokens = last_response.input_tokens if last_response else None
    run.output_tokens = last_response.output_tokens if last_response else None
    run.completed_at = datetime.now(UTC)
    await session.commit()
    raise StoryGenerationError(
        "生成内容在有限重试后仍未达到识字覆盖和儿童内容要求，请重试或降低难度。",
        category="validation_failed",
    )
