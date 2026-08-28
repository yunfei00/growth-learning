"""English Foundation V1 API contracts."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EnglishState = Literal["unlearned", "introduced", "practicing", "proficient", "stable"]
EnglishKindValue = Literal["letter", "word", "phonics", "phrase"]
EnglishMode = Literal["practice", "assessment"]
EnglishDimension = Literal[
    "listening",
    "meaning",
    "speaking",
    "uppercase_recognition",
    "lowercase_recognition",
    "case_matching",
    "letter_name",
    "sound_recognition",
    "grapheme_sound",
    "blending",
    "decoding",
    "expression",
]


class EnglishAudioResponse(BaseModel):
    strategy: Literal["curated", "tts", "safe_example_word", "phonics_unavailable"]
    accent: str
    speech_text: str | None
    audio_url: str | None
    instruction_zh: str
    available: bool


class EnglishVisualResponse(BaseModel):
    visual_type: Literal["static_image", "icon", "color_swatch", "shape", "emoji_fallback"]
    image_url: str | None
    visual_key: str | None
    source: str
    license: str
    attribution: str | None
    fallback: bool


class EnglishItemSummary(BaseModel):
    knowledge_point_id: uuid.UUID
    canonical_key: str
    kind: EnglishKindValue
    text: str
    normalized_text: str
    meaning_zh: str
    category: str
    category_label: str
    order_index: int
    status: Literal["active", "archived"]
    audio: EnglishAudioResponse
    visual: EnglishVisualResponse
    practice_count: int
    state_code: EnglishState
    learned: bool


class EnglishItemPage(BaseModel):
    items: list[EnglishItemSummary]
    page: int
    page_size: int
    total: int
    pages: int


class EnglishPracticeSummary(BaseModel):
    id: uuid.UUID
    template_key: str
    practice_kind: str
    generator_version: str
    status: Literal["active", "archived"]


class EnglishNavigationItem(BaseModel):
    knowledge_point_id: uuid.UUID
    text: str


class EnglishItemDetail(EnglishItemSummary):
    child_hint_zh: str
    parent_tip: str
    example_text: str | None
    example_meaning_zh: str | None
    image_key: str | None
    visual_key: str | None
    visual_type: Literal["static_image", "icon", "color_swatch", "shape", "emoji_fallback"]
    audio_key: str | None
    metadata: dict[str, object]
    catalog_version: str
    practices: list[EnglishPracticeSummary]
    position: int
    total: int
    previous: EnglishNavigationItem | None
    next: EnglishNavigationItem | None
    policy_key: str
    dimensions: dict[str, object]
    mastery_explanation: list[str]
    last_learning_at: datetime | None
    last_assessed_at: datetime | None
    next_review_at: datetime | None


class EnglishOverviewGroup(BaseModel):
    kind: EnglishKindValue
    label: str
    total: int
    learned: int
    proficient: int
    stable: int
    state_code: EnglishState


class EnglishOverviewResponse(BaseModel):
    child_id: uuid.UUID
    catalog_version: str
    total: int
    learned: int
    stable: int
    understood_words: int
    stable_words: int
    speaking_observed: int
    letters_learned: int
    letters_total: int
    phonics_practicing: int
    phrases_learned: int
    groups: list[EnglishOverviewGroup]


class EnglishSessionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_point_id: uuid.UUID
    mode: EnglishMode = "practice"
    exercise_count: int = Field(default=3, ge=1, le=8)
    dimension: EnglishDimension | None = None
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)


class EnglishProblemResponse(BaseModel):
    attempt_id: uuid.UUID
    template_key: str
    generator_version: str
    seed: int | None
    practice_kind: str
    dimension: str
    prompt: dict[str, object]
    options: list[dict[str, object]]
    answered: bool


class EnglishSessionResponse(BaseModel):
    session_id: uuid.UUID
    child_id: uuid.UUID
    knowledge_point_id: uuid.UUID
    item_text: str
    item_kind: EnglishKindValue
    mode: EnglishMode
    dimension: str
    problems: list[EnglishProblemResponse]
    completed_count: int
    total_count: int
    completed: bool


class EnglishAttemptAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submitted_answer: object
    hint_used: bool = False
    audio_replays: int = Field(default=0, ge=0, le=100)
    response_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class EnglishAttemptAnswerResponse(BaseModel):
    attempt_id: uuid.UUID
    outcome: Literal["correct", "hinted_correct", "uncertain", "incorrect"]
    first_answer_correct: bool
    attempt_count: int
    hint_used: bool
    audio_replay_count: int
    feedback: str
    session_completed: bool
    mastery_state: EnglishState | None


class EnglishSpeakingObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: Literal["willing_to_repeat", "can_say", "needs_prompt", "not_yet"]


class EnglishSpeakingObservationResponse(BaseModel):
    assessment_item_id: uuid.UUID
    dimension: Literal["speaking", "expression"]
    outcome: Literal["correct", "hinted_correct", "uncertain", "incorrect"]
    mastery_state: EnglishState


class EnglishTodayItem(EnglishItemSummary):
    item_kind: Literal["new", "review"]
    exercise_count: int
    completed: bool


class EnglishTodayResponse(BaseModel):
    plan_id: uuid.UUID
    child_id: uuid.UUID
    plan_date: date
    items: list[EnglishTodayItem]
    completed_count: int
    target_count: int
    status: Literal["pending", "in_progress", "completed"]
    estimated_minutes: int


class EnglishHistoryEvidence(BaseModel):
    knowledge_point_id: uuid.UUID
    text: str
    kind: EnglishKindValue
    dimension: str
    problem_count: int
    correct: int
    hinted_correct: int
    uncertain: int
    incorrect: int
    speaking_observations: int


class EnglishHistoryItem(BaseModel):
    session_id: uuid.UUID
    mode: Literal["practice", "assessment", "observation"]
    actor_display_name: str
    occurred_at: datetime
    evidence: list[EnglishHistoryEvidence]


class EnglishHistoryResponse(BaseModel):
    child_id: uuid.UUID
    items: list[EnglishHistoryItem]


class EnglishItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meaning_zh: str | None = Field(default=None, min_length=1, max_length=240)
    child_hint_zh: str | None = Field(default=None, min_length=1, max_length=1000)
    parent_tip: str | None = Field(default=None, min_length=1, max_length=2000)
    example_text: str | None = Field(default=None, min_length=1, max_length=240)
    example_meaning_zh: str | None = Field(default=None, min_length=1, max_length=240)
    category: str | None = Field(default=None, min_length=1, max_length=60)
    image_key: str | None = Field(default=None, max_length=255)
    visual_key: str | None = Field(default=None, max_length=160)
    visual_type: (
        Literal["static_image", "icon", "color_swatch", "shape", "emoji_fallback"] | None
    ) = None
    audio_key: str | None = Field(default=None, max_length=255)
    status: Literal["active", "archived"] | None = None


class EnglishImportResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    practice_items_created: int
    catalog_version: str
    catalog_size: int
    letter_count: int
    word_count: int
    phonics_count: int
    phrase_count: int
    practice_item_count: int
    course_created: bool
    errors: list[str]
