"""Growth timeline, report, book, media, and export API contracts."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GrowthCategoryValue = Literal[
    "learning",
    "assessment",
    "reading",
    "science",
    "family",
    "original_words",
    "achievement",
    "report",
]
GrowthEventTypeValue = Literal[
    "learning_milestone",
    "assessment_milestone",
    "reading_milestone",
    "science_milestone",
    "original_words",
    "manual_growth_note",
    "family_observation",
    "achievement",
    "report_marker",
]
GrowthPeriodValue = Literal["monthly", "yearly", "custom"]


class GrowthMediaResponse(BaseModel):
    id: uuid.UUID
    media_kind: Literal["image", "video", "audio"]
    mime_type: str
    size_bytes: int
    original_filename: str
    created_at: datetime
    content_url: str


class GrowthEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occurred_at: datetime
    title: str | None = Field(default=None, max_length=160)
    text: str = Field(min_length=1, max_length=5000)
    event_type: Literal["manual_growth_note", "family_observation"] = "manual_growth_note"
    category: Literal["family", "learning", "reading", "science"] = "family"

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("text")
    @classmethod
    def preserve_nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Growth record text cannot be blank")
        return value


class GrowthEventResponse(BaseModel):
    id: uuid.UUID
    child_id: uuid.UUID
    event_type: GrowthEventTypeValue
    category: GrowthCategoryValue
    occurred_at: datetime
    title: str
    body: str
    source_type: Literal["system", "parent", "companion", "teacher"]
    actor_user_id: uuid.UUID | None
    actor_display_name: str | None
    source_entity_type: str | None
    source_entity_id: uuid.UUID | None
    source_url: str | None
    evidence_snapshot: dict[str, object]
    policy_version: str
    archived_at: datetime | None
    media: list[GrowthMediaResponse]


class GrowthEventPage(BaseModel):
    items: list[GrowthEventResponse]
    page: int
    page_size: int
    total: int
    pages: int


class GrowthProjectionResult(BaseModel):
    created: int
    existing: int
    policy_version: str


class GrowthReportGenerate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_type: GrowthPeriodValue
    period_start: date
    period_end: date
    include_ai_narrative: bool = False

    @model_validator(mode="after")
    def validate_period(self) -> "GrowthReportGenerate":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        if (self.period_end - self.period_start).days > 730:
            raise ValueError("Report periods cannot exceed two years")
        return self


class GrowthReportVersionResponse(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    version_number: int
    period_type: GrowthPeriodValue
    period_start: date
    period_end: date
    generated_at: datetime
    source_cutoff_at: datetime
    policy_version: str
    metrics: dict[str, object]
    sections: dict[str, object]
    selected_event_ids: list[uuid.UUID]
    ai_narrative: str | None
    ai_provider: str | None
    ai_model: str | None
    ai_prompt_version: str | None


class GrowthReportSummary(BaseModel):
    id: uuid.UUID
    period_type: GrowthPeriodValue
    period_start: date
    period_end: date
    latest_version: int
    generated_at: datetime


class GrowthBookCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_type: Literal["yearly", "age_year"]
    edition_key: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=160)
    selected_event_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    selected_media: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    parent_message: str | None = Field(default=None, max_length=3000)

    @field_validator("title", "edition_key")
    @classmethod
    def clean_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value

    @field_validator("parent_message")
    @classmethod
    def clean_message(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class GrowthBookVersionResponse(BaseModel):
    id: uuid.UUID
    growth_book_id: uuid.UUID
    version_number: int
    edition_type: Literal["yearly", "age_year"]
    edition_key: str
    title: str
    selected_event_ids: list[uuid.UUID]
    selected_media: list[dict[str, str]]
    snapshot: dict[str, object]
    parent_message: str | None
    message_author_user_id: uuid.UUID | None
    message_recorded_at: datetime | None
    created_at: datetime


class GrowthBookSummary(BaseModel):
    id: uuid.UUID
    edition_type: Literal["yearly", "age_year"]
    edition_key: str
    latest_version: int
    title: str
    created_at: datetime


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    child_id: uuid.UUID | None = None


class ExportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    child_id: uuid.UUID | None
    requested_by_user_id: uuid.UUID
    status: Literal["pending", "processing", "completed", "failed", "expired"]
    schema_version: str
    size_bytes: int | None
    checksum_sha256: str | None
    failure_reason: str | None
    completed_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    download_url: str | None = None
