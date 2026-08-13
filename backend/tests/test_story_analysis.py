"""Pure coverage-policy tests: no provider, database, or LLM is involved."""

import pytest

from app.models import StoryDifficulty
from app.services.story_analysis import (
    ANALYZER_VERSION,
    PROFILES,
    analyze_story_coverage,
    extract_han,
    story_feasibility,
    validate_story_coverage,
)


def test_han_extraction_ignores_punctuation_spaces_latin_and_numerals() -> None:
    assert extract_han("小熊，2026 去 A-1 山！\n河。") == ["小", "熊", "去", "山", "河"]


def test_occurrence_and_unique_coverage_are_computed_separately() -> None:
    analysis = analyze_story_coverage(
        title="小山",
        paragraphs=["小小人去山河熊，123。"],
        strong_known={"小", "人", "去"},
        usable_recognizing={"河"},
        targets={"山"},
    )
    assert ANALYZER_VERSION == "han-coverage-v1"
    assert analysis.total_han_occurrences == 9
    assert analysis.unique_han_count == 6
    assert analysis.strong_known_occurrences == 5
    assert analysis.usable_recognizing_occurrences == 1
    assert analysis.target_occurrences == 2
    assert analysis.unexpected_occurrences == 1
    assert analysis.strong_known_coverage == 0.5556
    assert analysis.usable_known_coverage == 0.6667
    assert analysis.target_coverage == 0.2222
    assert analysis.unexpected_characters == ("熊",)


@pytest.mark.parametrize(
    ("difficulty", "known_count", "target_count"),
    [
        (StoryDifficulty.BEGINNER, 90, 10),
        (StoryDifficulty.NORMAL, 90, 10),
        (StoryDifficulty.CHALLENGE, 80, 20),
    ],
)
def test_each_profile_accepts_documented_deterministic_ratio(
    difficulty: str, known_count: int, target_count: int
) -> None:
    known_chars = list("人大小上下日月水火山木田土子女天中手口")
    target_chars = {"河", "船"}
    text = "".join(known_chars[index % len(known_chars)] for index in range(known_count))
    text += "".join(list(target_chars)[index % 2] for index in range(target_count))
    analysis = analyze_story_coverage(
        title="",
        paragraphs=[text],
        strong_known=set(known_chars),
        usable_recognizing=set(),
        targets=target_chars,
    )
    validation = validate_story_coverage(analysis, difficulty, target_chars)
    assert validation.accepted, validation.reasons


def test_profile_rejects_missing_targets_unexpected_text_and_gibberish() -> None:
    analysis = analyze_story_coverage(
        title="人山",
        paragraphs=["人" * 50 + "鬼" * 10],
        strong_known={"人"},
        usable_recognizing=set(),
        targets={"山", "河"},
    )
    validation = validate_story_coverage(analysis, StoryDifficulty.BEGINNER, {"山", "河"})
    assert validation.accepted is False
    assert "required_target_missing" in validation.reasons
    assert "unexpected_coverage_too_high" in validation.reasons
    assert "story_vocabulary_too_repetitive" in validation.reasons


def test_insufficient_literacy_threshold_is_explicit_per_profile() -> None:
    assert story_feasibility(StoryDifficulty.BEGINNER, 19) is not None
    assert story_feasibility(StoryDifficulty.BEGINNER, 20) is None
    assert story_feasibility(StoryDifficulty.NORMAL, 29) is not None
    assert story_feasibility(StoryDifficulty.CHALLENGE, 39) is not None
    assert PROFILES[StoryDifficulty.CHALLENGE].target_known == 0.80
