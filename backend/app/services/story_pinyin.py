"""Context-aware inline pinyin for assisted story reading.

This module is deliberately separate from the canonical mastery catalog. A story
may contain Han characters outside the 1200-character learning path, and inline
reading assistance must still be able to show their pronunciation without
creating fake knowledge points or mastery evidence.
"""

from __future__ import annotations

from pypinyin import Style, lazy_pinyin

from app.services.story_analysis import HAN_PATTERN


def _fallback_character_pinyin(character: str) -> str | None:
    if not HAN_PATTERN.fullmatch(character):
        return None
    values = lazy_pinyin(character, style=Style.TONE, neutral_tone_with_five=False)
    return values[0] if values else None


def annotate_paragraph_pinyin(paragraph: str) -> list[str | None]:
    """Return one pinyin slot per source character, using paragraph context.

    Calling pypinyin on the whole paragraph lets its phrase dictionary resolve
    readings such as ``开心地`` -> ``kāi xīn de``. Non-Han positions are kept as
    ``None`` so the result remains index-aligned with the original paragraph.
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
        return [_fallback_character_pinyin(character) for character in paragraph]

    return [
        reading if HAN_PATTERN.fullmatch(character) else None
        for character, reading in zip(paragraph, converted, strict=True)
    ]


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
