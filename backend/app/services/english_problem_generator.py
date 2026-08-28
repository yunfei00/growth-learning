"""Deterministic English exercise snapshots generated from canonical items."""

import random
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EnglishItem, EnglishPracticeItem, KnowledgePoint
from app.services.english_audio import english_audio_provider
from app.services.english_catalog import ENGLISH_GENERATOR_VERSION
from app.services.english_visual import english_visual_provider


@dataclass(frozen=True)
class GeneratedEnglishProblem:
    template_key: str
    generator_version: str
    seed: int
    practice_kind: str
    dimension: str
    prompt: dict[str, object]
    options: list[dict[str, object]]
    expected_answer: object


async def _load_items(
    session: AsyncSession, canonical_keys: list[str]
) -> dict[str, tuple[KnowledgePoint, EnglishItem]]:
    rows = (
        await session.execute(
            select(KnowledgePoint, EnglishItem)
            .join(EnglishItem, EnglishItem.knowledge_point_id == KnowledgePoint.id)
            .where(KnowledgePoint.canonical_key.in_(canonical_keys))
        )
    ).all()
    return {point.canonical_key: (point, item) for point, item in rows}


def _audio(item: EnglishItem) -> dict[str, object]:
    return asdict(english_audio_provider.resolve(item))


def _visual(item: EnglishItem) -> dict[str, object]:
    return asdict(english_visual_provider.resolve(item))


def _option(
    key: str,
    item: EnglishItem,
    *,
    position: int,
    include_visual: bool,
    include_audio: bool,
    reveal_text: bool,
) -> dict[str, object]:
    result: dict[str, object] = {
        "value": key,
        "position": position,
        "assessment_alt": f"选项{position + 1}",
    }
    if include_visual:
        result["visual"] = _visual(item)
    if include_audio:
        result["audio"] = _audio(item)
    if reveal_text:
        result["text"] = item.text
    return result


async def generate_english_problem(
    session: AsyncSession,
    practice: EnglishPracticeItem,
    seed: int,
) -> GeneratedEnglishProblem:
    if practice.generator_version != ENGLISH_GENERATOR_VERSION:
        raise ValueError("Unsupported English generator version")
    config = practice.config_json or {}
    target_key = str(config.get("target_key", ""))
    distractor_keys = [str(value) for value in config.get("distractor_keys", [])]
    rng = random.Random(seed)
    chosen_distractors = rng.sample(distractor_keys, k=min(2, len(distractor_keys)))
    keys = [target_key, *chosen_distractors]
    rows = await _load_items(session, keys)
    if target_key not in rows or len(rows) < 3:
        raise LookupError("English exercise content is incomplete")
    rng.shuffle(keys)
    target = rows[target_key][1]
    kind = practice.practice_kind
    dimension = str(config.get("dimension", "listening"))
    prompt: dict[str, object] = {
        "instruction": "听一听，是哪个？",
        "hide_target_text": True,
        "audio": _audio(target),
    }
    options: list[dict[str, object]] = []
    for position, key in enumerate(keys):
        item = rows[key][1]
        options.append(
            _option(
                key,
                item,
                position=position,
                include_visual=True,
                include_audio=False,
                reveal_text=False,
            )
        )

    if kind == "visual_choose_audio":
        prompt = {
            "instruction": "看看图片，哪个声音和它是一对？",
            "visual": _visual(target),
            "hide_target_text": True,
        }
        options = [
            _option(
                key,
                rows[key][1],
                position=position,
                include_visual=False,
                include_audio=True,
                reveal_text=False,
            )
            for position, key in enumerate(keys)
        ]
    elif kind == "letter_match":
        prompt = {
            "instruction": "听字母名称，找到这个字母。",
            "audio": _audio(target),
            "hide_target_text": True,
        }
        options = [
            _option(
                key,
                rows[key][1],
                position=position,
                include_visual=False,
                include_audio=False,
                reveal_text=True,
            )
            for position, key in enumerate(keys)
        ]
    elif kind == "case_match":
        prompt = {
            "instruction": "哪个小写字母和它是一对？",
            "text": target.text,
            "hide_target_text": False,
        }
        options = []
        for position, key in enumerate(keys):
            item = rows[key][1]
            option = _option(
                key,
                item,
                position=position,
                include_visual=False,
                include_audio=False,
                reveal_text=False,
            )
            option["text"] = str(item.metadata_json.get("lowercase", item.text.lower()))
            options.append(option)
    elif kind == "phonics_choose":
        prompt = {
            "instruction": target.child_hint_zh,
            "audio": _audio(target),
            "visual": _visual(target),
            "hide_target_text": True,
        }
        options = []
        for position, key in enumerate(keys):
            item = rows[key][1]
            option = _option(
                key,
                item,
                position=position,
                include_visual=False,
                include_audio=False,
                reveal_text=False,
            )
            option["text"] = str(item.metadata_json.get("grapheme", item.text))
            options.append(option)
    elif kind == "blending":
        prompt = {
            "instruction": "把声音慢慢连起来，是哪个单词？",
            "segments": list(target.metadata_json.get("segments", list(target.text))),
            "audio": _audio(target),
            "visual": _visual(target),
            "hide_target_text": True,
        }
        options = [
            _option(
                key,
                rows[key][1],
                position=position,
                include_visual=False,
                include_audio=False,
                reveal_text=True,
            )
            for position, key in enumerate(keys)
        ]
    elif kind == "phrase_listening":
        prompt = {
            "instruction": "听一听，这句话适合哪幅画面？",
            "audio": _audio(target),
            "hide_target_text": True,
        }
        options = [
            _option(
                key,
                rows[key][1],
                position=position,
                include_visual=True,
                include_audio=False,
                reveal_text=False,
            )
            for position, key in enumerate(keys)
        ]
    return GeneratedEnglishProblem(
        template_key=practice.template_key,
        generator_version=practice.generator_version,
        seed=seed,
        practice_kind=kind,
        dimension=dimension,
        prompt=prompt,
        options=options,
        expected_answer=target_key,
    )
