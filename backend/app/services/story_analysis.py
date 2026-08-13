"""Deterministic Han extraction, coverage metrics, and V1 acceptance policy."""

import re
from collections import Counter
from dataclasses import dataclass

from app.models import StoryDifficulty

ANALYZER_VERSION = "han-coverage-v1"
COVERAGE_POLICY_VERSION = "story-coverage-v1"
HAN_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


@dataclass(frozen=True)
class CoverageProfile:
    target_known: float
    min_known: float
    max_known: float
    min_target: float
    max_target: float
    max_unexpected: float
    minimum_occurrences: int
    minimum_unique_characters: int
    minimum_strong_known_characters: int


PROFILES: dict[str, CoverageProfile] = {
    StoryDifficulty.BEGINNER: CoverageProfile(0.95, 0.90, 0.98, 0.02, 0.10, 0.03, 30, 8, 20),
    StoryDifficulty.NORMAL: CoverageProfile(0.90, 0.84, 0.94, 0.06, 0.16, 0.04, 40, 10, 30),
    StoryDifficulty.CHALLENGE: CoverageProfile(0.80, 0.72, 0.86, 0.12, 0.25, 0.06, 50, 12, 40),
}


@dataclass(frozen=True)
class CoverageAnalysis:
    occurrences: tuple[str, ...]
    occurrence_counts: dict[str, int]
    total_han_occurrences: int
    unique_han_count: int
    strong_known_occurrences: int
    usable_recognizing_occurrences: int
    target_occurrences: int
    unexpected_occurrences: int
    strong_known_coverage: float
    usable_known_coverage: float
    target_coverage: float
    unexpected_coverage: float
    unique_known_coverage: float
    unexpected_characters: tuple[str, ...]


@dataclass(frozen=True)
class CoverageValidation:
    accepted: bool
    reasons: tuple[str, ...]


def extract_han(text: str) -> list[str]:
    """Extract Han occurrences; punctuation, spaces, Latin text, and numerals are ignored."""
    return HAN_PATTERN.findall(text)


def analyze_story_coverage(
    *,
    title: str,
    paragraphs: list[str],
    strong_known: set[str],
    usable_recognizing: set[str],
    targets: set[str],
) -> CoverageAnalysis:
    """Analyze title plus paragraphs. Sets are mutually classified target-first."""
    occurrences = tuple(extract_han("\n".join([title, *paragraphs])))
    counts = Counter(occurrences)
    total = len(occurrences)
    unexpected = set(counts) - strong_known - usable_recognizing - targets
    strong_count = sum(count for char, count in counts.items() if char in strong_known)
    recognizing_count = sum(
        count
        for char, count in counts.items()
        if char in usable_recognizing and char not in targets
    )
    target_count = sum(count for char, count in counts.items() if char in targets)
    unexpected_count = sum(counts[char] for char in unexpected)
    known_unique = (set(counts) & (strong_known | usable_recognizing)) - targets
    unique_total = len(counts)

    def ratio(value: int, denominator: int) -> float:
        return round(value / denominator, 4) if denominator else 0.0

    return CoverageAnalysis(
        occurrences=occurrences,
        occurrence_counts=dict(counts),
        total_han_occurrences=total,
        unique_han_count=unique_total,
        strong_known_occurrences=strong_count,
        usable_recognizing_occurrences=recognizing_count,
        target_occurrences=target_count,
        unexpected_occurrences=unexpected_count,
        strong_known_coverage=ratio(strong_count, total),
        usable_known_coverage=ratio(strong_count + recognizing_count, total),
        target_coverage=ratio(target_count, total),
        unexpected_coverage=ratio(unexpected_count, total),
        unique_known_coverage=ratio(len(known_unique), unique_total),
        unexpected_characters=tuple(sorted(unexpected)),
    )


def validate_story_coverage(
    analysis: CoverageAnalysis, difficulty: str, required_targets: set[str]
) -> CoverageValidation:
    profile = PROFILES[difficulty]
    reasons: list[str] = []
    if analysis.total_han_occurrences < profile.minimum_occurrences:
        reasons.append("story_too_short")
    if analysis.unique_han_count < profile.minimum_unique_characters:
        reasons.append("story_vocabulary_too_repetitive")
    if not profile.min_known <= analysis.usable_known_coverage <= profile.max_known:
        reasons.append("known_coverage_out_of_range")
    if not profile.min_target <= analysis.target_coverage <= profile.max_target:
        reasons.append("target_coverage_out_of_range")
    if analysis.unexpected_coverage > profile.max_unexpected:
        reasons.append("unexpected_coverage_too_high")
    missing = required_targets - set(analysis.occurrences)
    if missing:
        reasons.append("required_target_missing")
    return CoverageValidation(accepted=not reasons, reasons=tuple(reasons))


def story_feasibility(difficulty: str, strong_known_count: int) -> str | None:
    profile = PROFILES[difficulty]
    if strong_known_count >= profile.minimum_strong_known_characters:
        return None
    return (
        "当前识字基础不足以生成该难度的独立阅读故事。建议降低难度、选择家长陪读，或先继续识字学习。"
    )
