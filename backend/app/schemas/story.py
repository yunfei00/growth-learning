"""Validated story generation, reading, and comprehension contracts."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

StoryDifficultyValue = Literal["beginner", "normal", "challenge"]
ReadingModeValue = Literal["independent", "with_help"]
ReadingStatusValue = Literal["in_progress", "completed", "abandoned"]
ReadingOutcomeValue = Literal["correct", "with_help", "partial", "incorrect"]


class GeneratedReadingQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=240)
    options: list[str] = Field(min_length=2, max_length=4)
    correct_option_index: int = Field(ge=0)

    @model_validator(mode="after")
    def answer_must_exist(self) -> "GeneratedReadingQuestion":
        if self.correct_option_index >= len(self.options):
            raise ValueError("correct_option_index must reference an option")
        return self


class GeneratedStoryPayload(BaseModel):
    """The only provider response shape accepted by the story pipeline."""

    title: str = Field(min_length=2, max_length=120)
    paragraphs: list[str] = Field(min_length=1, max_length=8)
    summary: str | None = Field(default=None, max_length=300)
    questions: list[GeneratedReadingQuestion] = Field(min_length=2, max_length=3)

    @field_validator("paragraphs")
    @classmethod
    def validate_paragraphs(cls, paragraphs: list[str]) -> list[str]:
        cleaned = [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]
        if len(cleaned) != len(paragraphs):
            raise ValueError("paragraphs cannot be blank")
        return cleaned


class StoryGenerationRequest(BaseModel):
    difficulty: StoryDifficultyValue = "beginner"
    theme: str = Field(default="animals", min_length=2, max_length=40)
    custom_theme: str | None = Field(default=None, max_length=80)
    target_knowledge_point_ids: list[uuid.UUID] | None = Field(
        default=None, min_length=2, max_length=5
    )
    request_key: str | None = Field(default=None, min_length=8, max_length=80)
    story_id: uuid.UUID | None = None


class CoverageMetricsResponse(BaseModel):
    analyzer_version: str
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
    unexpected_characters: list[str]


class MasteryCharacterResponse(BaseModel):
    knowledge_point_id: uuid.UUID
    character: str
    mastery_level: str
    is_priority: bool


class StoryGenerationContextResponse(BaseModel):
    child_id: uuid.UUID
    age_band: str
    provider_configured: bool
    provider: str
    model: str
    recommended_difficulty: StoryDifficultyValue | None
    strong_known_count: int
    usable_recognizing_count: int
    automatic_targets: list[MasteryCharacterResponse]
    safe_themes: list[str]
    catalog_size: int
    catalog_limitation: str
    feasibility_message: str | None


class ReadingQuestionResponse(BaseModel):
    id: uuid.UUID
    position: int
    question: str
    options: list[str]


class CharacterGlossaryResponse(BaseModel):
    knowledge_point_id: uuid.UUID
    character: str
    pinyin: str
    simple_meaning: str | None
    common_words: list[str]


class StoryVersionResponse(BaseModel):
    id: uuid.UUID
    story_id: uuid.UUID
    version_number: int
    title: str
    paragraphs: list[str]
    summary: str | None
    theme: str
    custom_theme: str | None
    difficulty: StoryDifficultyValue
    requested_known_coverage: float
    actual_strong_known_coverage: float
    actual_usable_known_coverage: float
    actual_target_coverage: float
    actual_unexpected_coverage: float
    unique_known_coverage: float
    total_han_occurrences: int
    unique_han_count: int
    unexpected_characters: list[str]
    target_characters: list[str]
    snapshot_at: datetime
    coverage_policy_version: str
    analyzer_version: str
    prompt_version: str
    provider: str
    model: str
    questions: list[ReadingQuestionResponse]
    glossary: list[CharacterGlossaryResponse]
    created_at: datetime


class StoryGenerationResponse(BaseModel):
    generation_run_id: uuid.UUID
    status: Literal["succeeded"]
    attempt_count: int
    version: StoryVersionResponse


class StoryListItemResponse(BaseModel):
    story_id: uuid.UUID
    story_version_id: uuid.UUID
    title: str
    theme: str
    difficulty: StoryDifficultyValue
    actual_known_coverage: float
    target_characters: list[str]
    generated_at: datetime
    reading_status: ReadingStatusValue | None
    reading_mode: ReadingModeValue | None
    comprehension_answered: int
    comprehension_total: int


class StoryPageResponse(BaseModel):
    items: list[StoryListItemResponse]
    page: int
    page_size: int
    total: int
    pages: int


class ReadingSessionStart(BaseModel):
    reading_mode: ReadingModeValue = "with_help"


class ReadingAnswerInput(BaseModel):
    question_id: uuid.UUID
    selected_option_index: int = Field(ge=0)
    outcome: ReadingOutcomeValue


class ReadingAnswersSubmit(BaseModel):
    answers: list[ReadingAnswerInput] = Field(min_length=1, max_length=3)

    @field_validator("answers")
    @classmethod
    def answers_are_unique(cls, answers: list[ReadingAnswerInput]) -> list[ReadingAnswerInput]:
        ids = [answer.question_id for answer in answers]
        if len(ids) != len(set(ids)):
            raise ValueError("question answers must be unique")
        return answers


class ReadingCompleteRequest(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=0, le=24 * 60 * 60)
    parent_note: str | None = Field(default=None, max_length=1000)


class ReadingAnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: uuid.UUID
    selected_option_index: int
    outcome: ReadingOutcomeValue
    answered_at: datetime


class ReadingSessionResponse(BaseModel):
    id: uuid.UUID
    child_id: uuid.UUID
    story_version_id: uuid.UUID
    reading_mode: ReadingModeValue
    status: ReadingStatusValue
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: int | None
    parent_note: str | None
    answers: list[ReadingAnswerResponse]
    story_exposure_count: int


class ReadingSummaryResponse(BaseModel):
    stories_read_this_week: int
    independent_this_week: int
    with_help_this_week: int
    comprehension_correct: int
    comprehension_answered: int
    comprehension_message: str
    target_exposure_count: int


class DailyReadingTaskResponse(BaseModel):
    status: Literal["needs_story", "pending", "in_progress", "completed"]
    target_count: int = 1
    story_version_id: uuid.UUID | None
    reading_session_id: uuid.UUID | None
    title: str | None
