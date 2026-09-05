"""API contracts for representative Chinese-character literacy diagnostics."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.learning import SpeechAttemptResponse

DiagnosticOutcomeValue = Literal["correct", "uncertain", "incorrect"]
DiagnosticEvaluationMethodValue = Literal["parent_manual", "speech_assisted"]
DiagnosticStatusValue = Literal["in_progress", "completed", "abandoned"]


class LiteracyDiagnosticItemSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_point_id: uuid.UUID
    outcome: DiagnosticOutcomeValue
    response_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    evaluation_method: DiagnosticEvaluationMethodValue = "parent_manual"
    speech_attempt_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)


class LiteracyDiagnosticBatchSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LiteracyDiagnosticItemSubmit] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_items(self) -> "LiteracyDiagnosticBatchSubmit":
        ids = [item.knowledge_point_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("A character can appear only once per diagnostic submission")
        return self


class LiteracyDiagnosticTargetResponse(BaseModel):
    knowledge_point_id: uuid.UUID
    character: str
    pinyin: str
    position: int
    sampling_class: str
    outcome: DiagnosticOutcomeValue | None = None
    assessment_item_id: uuid.UUID | None = None
    response_time_ms: int | None = None
    evaluation_method: DiagnosticEvaluationMethodValue | None = None
    speech_attempts: list[SpeechAttemptResponse] = Field(default_factory=list)


class LiteracyDiagnosticResultResponse(BaseModel):
    assessment_session_id: uuid.UUID
    catalog_size: int
    catalog_version: str
    sample_size: int
    estimated_known: int
    lower_bound: int
    upper_bound: int
    directly_known: int
    uncertain: int
    unknown: int
    untested: int
    estimation_version: str
    limitation: str
    created_at: datetime


class LiteracyDiagnosticSessionResponse(BaseModel):
    id: uuid.UUID
    child_id: uuid.UUID
    source: Literal["literacy_diagnostic"] = "literacy_diagnostic"
    status: DiagnosticStatusValue
    sampling_method: str
    sampling_version: str
    eligible_catalog_size: int
    catalog_version: str
    segment_size: int
    total_segments: int
    current_segment: int
    segment_break_due: bool
    started_at: datetime
    completed_at: datetime | None
    total_items: int
    completed_items: int
    targets: list[LiteracyDiagnosticTargetResponse]
    result: LiteracyDiagnosticResultResponse | None = None


class LiteracyDiagnosticHistoryEntry(BaseModel):
    id: uuid.UUID
    status: DiagnosticStatusValue
    started_at: datetime
    completed_at: datetime | None
    total_items: int
    completed_items: int
    directly_known: int
    uncertain: int
    unknown: int
    result: LiteracyDiagnosticResultResponse | None = None


class LiteracyDiagnosticOverviewResponse(BaseModel):
    active_session: LiteracyDiagnosticSessionResponse | None = None
    latest_result: LiteracyDiagnosticResultResponse | None = None
    history: list[LiteracyDiagnosticHistoryEntry] = Field(default_factory=list)
    recommended_sample_size: int
    segment_size: int
    limitation: str
