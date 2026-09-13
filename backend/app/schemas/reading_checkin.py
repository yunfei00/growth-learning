"""Contracts for daily reading check-ins and child-initiated reading help."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ReadingHelpEventCreate(BaseModel):
    character: str = Field(min_length=1, max_length=8)

    @field_validator("character")
    @classmethod
    def one_character(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) != 1:
            raise ValueError("character must contain exactly one character")
        return cleaned


class ReadingHelpEventResponse(BaseModel):
    id: uuid.UUID
    reading_session_id: uuid.UUID
    character: str
    pinyin: str | None
    help_kind: Literal["character_tap"]
    occurred_at: datetime


class ReadingCheckinDayResponse(BaseModel):
    date: date
    completed: bool
    title: str | None
    story_version_id: uuid.UUID | None
    reading_session_id: uuid.UUID | None
    reading_mode: Literal["independent", "with_help"] | None
    duration_seconds: int | None
    help_count: int = 0
    help_characters: list[str] = Field(default_factory=list)


class ReadingCheckinSummaryResponse(BaseModel):
    from_date: date
    to_date: date
    today_completed: bool
    current_streak: int
    longest_streak: int
    completed_days: int
    total_duration_seconds: int
    total_help_count: int
    days: list[ReadingCheckinDayResponse]
