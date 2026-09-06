"""Context-aware inline pinyin for assisted story reading.

This module is deliberately separate from the canonical mastery catalog. A story
may contain Han characters outside the 1200-character learning path, and inline
reading assistance must still be able to show their pronunciation without
creating fake knowledge points or mastery evidence.
"""

from __future__ import annotations

import re

from pypinyin import Style, lazy_pinyin

from app.services.story_analysis import HAN_PATTERN

# pypinyin deliberately follows dictionary readings and does not consistently
# infer the grammatical particle reading for 地.  For a children's reader we
# prefer a small, deterministic correction layer over sending text to an LLM or
# silently teaching ``dì`` in common adverbial phrases.
_STRUCTURAL_DE_MODIFIERS = (
    "开心",
    "高兴",
    "快乐",
    "认真",
    "仔细",
    "小心",
    "努力",
    "勇敢",
    "温柔",
    "好奇",
    "急忙",
    "安静",
    "大声",
    "轻声",
    "飞快",
    "悄悄",
    "偷偷",
    "轻轻",
    "慢慢",
    "静静",
    "紧紧",
    "稳稳",
    "快快",
)
_STRUCTURAL_DE_PATTERN = re.compile(
    rf"(?:{'|'.join(map(re.escape, _STRUCTURAL_DE_MODIFIERS))})地(?=[\u3400-\u4dbf\u4e00-\u9fff])"
)
_REPEATED_MODIFIER_PATTERN = re.compile(
    r"(?:([\u3400-\u4dbf\u4e00-\u9fff])\1|"
    r"([\u3400-\u4dbf\u4e00-\u9fff])([\u3400-\u4dbf\u4e00-\u9fff])\2\3)"
    r"地(?=[\u3400-\u4dbf\u4e00-\u9fff])"
)


def _fallback_character_pinyin(character: str) -> str | None:
    if not HAN_PATTERN.fullmatch(character):
        return None
    values = lazy_pinyin(character, style=Style.TONE, neutral_tone_with_five=False)
    return values[0] if values else None


def _structural_de_indexes(paragraph: str) -> set[int]:
    indexes: set[int] = set()
    for pattern in (_STRUCTURAL_DE_PATTERN, _REPEATED_MODIFIER_PATTERN):
        for match in pattern.finditer(paragraph):
            index = match.end() - 1
            if paragraph[index] == "地":
                indexes.add(index)
    return indexes


def annotate_paragraph_pinyin(paragraph: str) -> list[str | None]:
    """Return one pinyin slot per source character, using paragraph context.

    Pypinyin is called on the whole paragraph so its phrase dictionary can
    resolve ordinary polyphonic words. A deterministic grammar correction then
    handles common adverbial ``…地 + 动作`` phrases, where pypinyin otherwise
    returns the standalone noun reading ``dì``. Non-Han positions remain
    ``None`` so the result stays index-aligned with the source text.
    """

    if not paragraph:
        return []

    converted = lazy_pinyin(
        paragraph,
        style=Style.TONE,
        neutral_tone_with_five=False,
        errors=lambda text: list(text),
    )
    if len(converted) != len(paragraph):
        annotated = [_fallback_character_pinyin(character) for character in paragraph]
    else:
        annotated = [
            reading if HAN_PATTERN.fullmatch(character) else None
            for character, reading in zip(paragraph, converted, strict=True)
        ]

    for index in _structural_de_indexes(paragraph):
        annotated[index] = "de"
    return annotated


def first_contextual_readings(paragraphs: list[str]) -> dict[str, str]:
    """Choose the first contextual reading for each Han character in a story.

    The existing reader glossary is character-based, while inline text is
    occurrence-based. This map lets the current glossary render complete pinyin
    now; future readers can consume ``annotate_paragraph_pinyin`` directly when
    they need multiple readings for the same polyphonic character in one story.
    """

    readings: dict[str, str] = {}
    for paragraph in paragraphs:
        annotated = annotate_paragraph_pinyin(paragraph)
        for character, reading in zip(paragraph, annotated, strict=True):
            if reading and HAN_PATTERN.fullmatch(character):
                readings.setdefault(character, reading)
    return readings
