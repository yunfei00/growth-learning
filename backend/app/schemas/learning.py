"""Child character learning, assessment, and mastery API schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SessionStatusValue = Literal["in_progress", "completed", "abandoned"]
ActivityTypeValue = Literal["introduced", "relearned", "parent_marked_seen"]
AssessmentOutcomeValue = Literal["correct", "hinted_correct", "uncertain", "incorrect"]
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
    def unique_items(self) -> "LearningSessionCreate":
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

    @model_validator(mode="after")
    def align_hint_outcome(self) -> "AssessmentItemInput":
        if self.outcome == "hinted_correct":
            self.hint_used = True
        return self


class AssessmentSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SessionStatusValue = "completed"
    source: str = Field(default="quick_recognition", min_length=1, max_length=40)
    items: list[AssessmentItemInput] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_items(self) -> "AssessmentSessionCreate":
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


class CharacterMasteryState(BaseModel):
    knowledge_point_id: uuid.UUID
    character: str
    pinyin: str
    common_words: list[str]
    simple_meaning: str | None
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


class PriorityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_priority: bool
