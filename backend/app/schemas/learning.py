"""Child character learning, assessment, and mastery API schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.story import DailyReadingTaskResponse

SessionStatusValue = Literal["in_progress", "completed", "abandoned"]
ActivityTypeValue = Literal[
    "introduced",
    "relearned",
    "parent_marked_seen",
    "guided_practice",
    "independent_practice",
    "reviewed",
    "applied",
]
AssessmentOutcomeValue = Literal["correct", "hinted_correct", "uncertain", "incorrect"]
AssessmentEvaluationMethodValue = Literal["parent_manual", "speech_assisted"]
SpeechReviewDecisionValue = Literal[
    "match", "partial_match", "uncertain", "no_match", "no_speech", "recognition_error"
]
CharacterReviewModeValue = Literal["parent_manual", "speech_auto"]
AssessmentKindValue = Literal[
    "recognition",
    "practice_check",
    "listening_check",
    "oral_check",
    "math_check",
]
MasteryLevelValue = Literal["unlearned", "introduced", "recognizing", "proficient", "stable"]


class LearningRecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_point_id: uuid.UUID
    activity_type: ActivityTypeValue = "introduced"


class LearningSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SessionStatusValue = "completed"
    source: str = Field(default="parent_assisted", min_length=1, max_length=40)
    items: list[LearningRecordInput] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_items(self) -> LearningSessionCreate:
        ids = [item.knowledge_point_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("A knowledge point can appear only once per session")
        return self


class AssessmentItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_point_id: uuid.UUID
    outcome: AssessmentOutcomeValue
    response_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    hint_used: bool = False
    skill_dimension: str | None = Field(default=None, min_length=1, max_length=60)
    evidence_metadata: dict[str, object] = Field(default_factory=dict)
    evaluation_method: AssessmentEvaluationMethodValue = "parent_manual"
    speech_attempt_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def align_hint_outcome(self) -> AssessmentItemInput:
        if self.outcome == "hinted_correct":
            self.hint_used = True
        return self


class AssessmentSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SessionStatusValue = "completed"
    source: str = Field(default="quick_recognition", min_length=1, max_length=40)
    assessment_kind: AssessmentKindValue = "recognition"
    items: list[AssessmentItemInput] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_items(self) -> AssessmentSessionCreate:
        ids = [item.knowledge_point_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("A knowledge point can appear only once per session")
        return self


class EvidenceSessionResponse(BaseModel):
    id: uuid.UUID
    child_id: uuid.UUID
    status: SessionStatusValue
    source: str
    item_count: int
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    mastery_projection: Literal["configured", "partially_unavailable", "unavailable"]
    projection_unavailable_knowledge_point_ids: list[uuid.UUID] = Field(default_factory=list)


class CharacterMasteryState(BaseModel):
    knowledge_point_id: uuid.UUID
    character: str
    pinyin: str
    common_words: list[str]
    simple_meaning: str | None
    example_sentence: str | None
    parent_tip: str | None
    mastery_level: MasteryLevelValue
    mastery_score: float
    first_introduced_at: datetime | None
    last_learning_at: datetime | None
    last_assessed_at: datetime | None
    correct_count: int
    hinted_correct_count: int
    uncertain_count: int
    incorrect_count: int
    consecutive_correct: int
    consecutive_incorrect: int
    average_response_time_ms: float | None
    is_priority: bool
    algorithm_version: str


class CharacterMasteryPage(BaseModel):
    items: list[CharacterMasteryState]
    page: int
    page_size: int
    total: int
    pages: int


class CharacterMasterySummary(BaseModel):
    total_enabled: int
    unlearned: int
    introduced: int
    recognizing: int
    proficient: int
    stable: int
    priority: int
    learning_records: int
    assessment_items: int


class CharacterRecommendation(BaseModel):
    id: uuid.UUID
    character: str
    pinyin: str
    common_words: list[str]
    simple_meaning: str | None
    example_sentence: str | None
    mastery_level: MasteryLevelValue
    is_priority: bool


class TimelineItem(BaseModel):
    id: uuid.UUID
    evidence_type: Literal["learning", "assessment"]
    value: str
    occurred_at: datetime
    response_time_ms: int | None = None


class CharacterMasteryDetail(BaseModel):
    state: CharacterMasteryState
    timeline: list[TimelineItem]


class CharacterLearningHistoryRecord(BaseModel):
    record_id: uuid.UUID
    knowledge_point_id: uuid.UUID
    character: str
    pinyin: str
    activity_type: str
    source: str
    learned_at: datetime
    mastery_level: MasteryLevelValue
    is_priority: bool


class CharacterLearningHistorySession(BaseModel):
    session_id: uuid.UUID
    source: str
    status: SessionStatusValue
    started_at: datetime
    completed_at: datetime | None
    records: list[CharacterLearningHistoryRecord]


class CharacterLearningHistoryPage(BaseModel):
    items: list[CharacterLearningHistorySession]
    page: int
    page_size: int
    total_sessions: int
    total_records: int
    pages: int
    distinct_characters: int
    this_week_first_learned: int


class CharacterNavigationItem(BaseModel):
    knowledge_point_id: uuid.UUID
    character: str


class CharacterNavigationResponse(BaseModel):
    sequence: str
    position: int
    total: int
    group: int | None = None
    group_size: int | None = None
    previous: CharacterNavigationItem | None = None
    next: CharacterNavigationItem | None = None


class CharacterAIAssistanceResponse(BaseModel):
    simple_explanation: str
    words: list[str]
    example_sentence: str
    parent_tip: str
    provider: str
    model: str
    mastery_directly_modified: Literal[False] = False


class PriorityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_priority: bool


AssessmentSourceValue = Literal["quick_test", "daily_review", "weekly_check", "monthly_assessment"]
PlanStatusValue = Literal["pending", "in_progress", "completed"]


class LearningSettingsResponse(BaseModel):
    max_new_characters_per_day: int
    daily_review_capacity: int
    weekly_assessment_enabled: bool
    monthly_assessment_enabled: bool
    timezone: str
    character_review_mode: CharacterReviewModeValue
    speech_review_feature_enabled: bool = False


class LearningSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_new_characters_per_day: int | None = Field(default=None, ge=0, le=20)
    daily_review_capacity: int | None = Field(default=None, ge=1, le=100)
    weekly_assessment_enabled: bool | None = None
    monthly_assessment_enabled: bool | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    character_review_mode: CharacterReviewModeValue | None = None

    @model_validator(mode="after")
    def valid_timezone(self) -> LearningSettingsUpdate:
        if self.timezone is not None:
            try:
                ZoneInfo(self.timezone)
            except ZoneInfoNotFoundError as error:
                raise ValueError("Unknown IANA timezone") from error
        return self


class ReviewScheduleResponse(BaseModel):
    knowledge_point_id: uuid.UUID
    character: str
    pinyin: str
    last_review_at: datetime
    next_review_at: datetime
    interval_days: int
    interval_stage: int
    last_outcome: str
    scheduling_reason: str
    is_priority: bool
    overdue_days: int
    algorithm_version: str


class ReviewBacklogResponse(BaseModel):
    due_count: int
    selected_count: int
    capacity: int
    estimated_days_to_clear: int
    items: list[ReviewScheduleResponse]


class DailyPlanItemResponse(BaseModel):
    subject: Literal["chinese"] = "chinese"
    knowledge_point_id: uuid.UUID
    character: str
    pinyin: str
    common_words: list[str]
    simple_meaning: str | None
    example_sentence: str | None
    item_kind: Literal["new", "review"]
    status: Literal["pending", "completed"]
    position: int
    selection_reason: str


class DailyPlanResponse(BaseModel):
    id: uuid.UUID
    child_id: uuid.UUID
    plan_date: date
    timezone: str
    recommended_new_count: int
    review_count: int
    due_count: int
    estimated_backlog_days: int
    recommendation_reason: str
    new_completed_count: int
    review_completed_count: int
    status: PlanStatusValue
    recent_independent_correct_rate: float | None
    weekly_status: str
    monthly_status: str
    literacy_status: str
    literacy_estimate: float | None
    literacy_catalog_size: int
    items: list[DailyPlanItemResponse]
    reading: DailyReadingTaskResponse


class AssessmentTargetResponse(BaseModel):
    knowledge_point_id: uuid.UUID
    character: str
    pinyin: str
    position: int
    sampling_class: str
    outcome: AssessmentOutcomeValue | None = None
    assessment_item_id: uuid.UUID | None = None
    response_time_ms: int | None = None
    hint_requested_at: datetime | None = None
    evaluation_method: AssessmentEvaluationMethodValue = "parent_manual"
    speech_attempts: list[SpeechAttemptResponse] = Field(default_factory=list)
    override: AssessmentOverrideResponse | None = None


class SpeechAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript: str = Field(min_length=1, max_length=120)
    confidence: float | None = Field(default=None, ge=0, le=1)


class SpeechAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_point_id: uuid.UUID
    attempt_index: int = Field(ge=1, le=3)
    provider: str = Field(min_length=1, max_length=80)
    transcript: str | None = Field(default=None, max_length=120)
    alternatives: list[SpeechAlternative] = Field(default_factory=list, max_length=5)
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_available: bool = False
    duration_ms: int | None = Field(default=None, ge=0, le=60_000)
    decision: SpeechReviewDecisionValue
    normalized_readings: list[str] = Field(default_factory=list, max_length=20)
    syllable_match: bool | None = None
    tone_match: bool | None = None
    tone_evaluation: Literal["matched", "mismatched", "unavailable"] = "unavailable"
    explicit_unknown: bool = False
    hint_used: bool = False
    provider_metadata: dict[str, object] = Field(default_factory=dict)


class SpeechAttemptResponse(BaseModel):
    id: uuid.UUID
    attempt_index: int
    provider: str
    transcript: str | None
    alternatives: list[SpeechAlternative]
    confidence: float | None
    confidence_available: bool
    normalized_readings: list[str]
    decision: SpeechReviewDecisionValue
    syllable_match: bool | None
    tone_match: bool | None
    tone_evaluation: Literal["matched", "mismatched", "unavailable"]
    explicit_unknown: bool
    hint_used: bool
    duration_ms: int | None
    created_at: datetime


class SpeechPracticeEvaluate(BaseModel):
    """Privacy-minimal transcript payload for non-assessment oral practice."""

    model_config = ConfigDict(extra="forbid")

    transcript: str | None = Field(default=None, max_length=120)
    alternatives: list[SpeechAlternative] = Field(default_factory=list, max_length=5)
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_available: bool = False


class SpeechPracticeResponse(BaseModel):
    decision: SpeechReviewDecisionValue
    normalized_readings: list[str]
    syllable_match: bool | None
    tone_match: bool | None
    tone_evaluation: Literal["matched", "mismatched", "unavailable"]
    explicit_unknown: bool
    assessment_item_created: Literal[False] = False
    mastery_modified: Literal[False] = False


class AssessmentOverrideCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: AssessmentOutcomeValue
    reason: str = Field(min_length=1, max_length=500)


class AssessmentOverrideResponse(BaseModel):
    id: uuid.UUID
    original_outcome: AssessmentOutcomeValue
    override_outcome: AssessmentOutcomeValue
    overridden_by_user_id: uuid.UUID
    override_reason: str
    overridden_at: datetime


class PlannedAssessmentResponse(BaseModel):
    id: uuid.UUID
    child_id: uuid.UUID
    source: AssessmentSourceValue
    status: SessionStatusValue
    sampling_method: str
    sampling_version: str
    eligible_catalog_size: int
    catalog_version: str
    started_at: datetime
    completed_at: datetime | None
    total_items: int
    completed_items: int
    targets: list[AssessmentTargetResponse]


class AssessmentBatchSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AssessmentItemInput] = Field(default_factory=list, max_length=100)
    complete: bool = False

    @model_validator(mode="after")
    def unique_items(self) -> AssessmentBatchSubmit:
        ids = [item.knowledge_point_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("A knowledge point can appear only once per submission")
        if not self.items and not self.complete:
            raise ValueError("Submit at least one item or complete the session")
        return self


class AssessmentHistoryEntry(BaseModel):
    id: uuid.UUID
    source: AssessmentSourceValue
    status: SessionStatusValue
    started_at: datetime
    completed_at: datetime | None
    item_count: int
    correct: int
    hinted_correct: int
    uncertain: int
    incorrect: int


class LiteracyEstimateResponse(BaseModel):
    id: uuid.UUID | None
    assessment_session_id: uuid.UUID | None
    catalog_size: int
    catalog_version: str
    sample_size: int
    known_count: int
    unknown_count: int
    sampling_method: str | None
    sampling_version: str | None
    estimate: float | None
    lower_bound: float | None
    upper_bound: float | None
    is_sufficient: bool
    estimation_version: str
    limitation: str
    created_at: datetime | None
