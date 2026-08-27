"""API contracts for the child-friendly Pinyin learning system."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PinyinKindValue = Literal["initial", "final", "tone", "whole"]
PinyinStateValue = Literal["unlearned", "introduced", "practicing", "proficient", "stable"]
PinyinDimensionValue = Literal["recognition", "listening", "tone", "blending", "pronunciation"]


class PinyinAudioResponse(BaseModel):
    mode: Literal["curated", "tts_fallback", "missing"]
    audio_url: str | None
    speech_text: str | None


class PinyinItemSummary(BaseModel):
    knowledge_point_id: uuid.UUID
    symbol: str
    kind: PinyinKindValue
    subcategory: str
    display_text: str
    example_text: str | None
    order_index: int
    status: Literal["active", "archived"]
    audio_status: Literal["curated", "tts_fallback", "missing"]
    state_code: PinyinStateValue = "unlearned"
    learned: bool = False


class PinyinItemPage(BaseModel):
    items: list[PinyinItemSummary]
    page: int
    page_size: int
    total: int
    pages: int


class PinyinNavigationItem(BaseModel):
    knowledge_point_id: uuid.UUID
    display_text: str


class PinyinItemDetail(PinyinItemSummary):
    canonical_key: str
    pronunciation_cue: str | None
    example_pinyin: str | None
    description: str | None
    parent_tip: str | None
    audio_key: str | None = None
    catalog_version: str
    metadata: dict[str, object]
    audio: PinyinAudioResponse
    position: int
    total: int
    previous: PinyinNavigationItem | None
    next: PinyinNavigationItem | None
    confusing: list[PinyinNavigationItem]
    listening_options: list[PinyinNavigationItem]
    policy_key: str
    dimensions: dict[str, object]


class PinyinOverviewGroup(BaseModel):
    kind: PinyinKindValue
    label: str
    total: int
    learned: int
    stable: int


class PinyinOverviewResponse(BaseModel):
    child_id: uuid.UUID
    catalog_version: str
    total: int
    learned: int
    stable: int
    groups: list[PinyinOverviewGroup]
    blending_state: PinyinStateValue
    blending_attempts: int


class PinyinTodayResponse(BaseModel):
    plan_id: uuid.UUID
    child_id: uuid.UUID
    plan_date: date
    new_items: list[PinyinItemSummary]
    review_items: list[PinyinItemSummary]
    completed_count: int
    target_count: int
    status: Literal["pending", "in_progress", "completed"]


class PinyinPracticeResponse(BaseModel):
    id: uuid.UUID
    practice_key: str
    initial_knowledge_point_id: uuid.UUID
    final_knowledge_point_id: uuid.UUID
    initial: str
    underlying_final: str
    display_final: str
    display_syllable: str
    pronunciation_cue: str
    order_index: int
    metadata: dict[str, object]


class PinyinPracticePage(BaseModel):
    items: list[PinyinPracticeResponse]
    total: int


class PinyinHistoryEvidence(BaseModel):
    evidence_id: uuid.UUID
    evidence_type: Literal["learning", "assessment"]
    knowledge_point_id: uuid.UUID
    display_text: str
    dimension: str | None
    outcome: str
    occurred_at: datetime


class PinyinHistorySession(BaseModel):
    session_id: uuid.UUID
    source: str
    actor_display_name: str
    occurred_at: datetime
    evidence: list[PinyinHistoryEvidence]


class PinyinHistoryResponse(BaseModel):
    child_id: uuid.UUID
    items: list[PinyinHistorySession]


class PinyinItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "archived"] | None = None
    pronunciation_cue: str | None = Field(default=None, max_length=160)
    example_text: str | None = Field(default=None, max_length=120)
    example_pinyin: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    parent_tip: str | None = Field(default=None, max_length=2000)
    audio_key: str | None = Field(default=None, max_length=255)


class PinyinImportResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    relations_created: int
    practices_created: int
    catalog_version: str
    catalog_size: int
    course_created: bool
    errors: list[str]
