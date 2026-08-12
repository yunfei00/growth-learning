"""Schemas for canonical Chinese-character catalog operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_list(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class CharacterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character: str = Field(min_length=1, max_length=1)
    pinyin: str = Field(min_length=1, max_length=120)
    stroke_count: int | None = Field(default=None, ge=1, le=100)
    radical: str | None = Field(default=None, max_length=16)
    frequency_rank: int | None = Field(default=None, ge=1)
    difficulty_level: int | None = Field(default=None, ge=1, le=10)
    simple_meaning: str | None = None
    example_sentence: str | None = None
    common_words: list[str] = Field(default_factory=list, max_length=30)
    tags: list[str] = Field(default_factory=list, max_length=30)
    is_enabled: bool = True
    source_type: str = Field(default="manual", min_length=1, max_length=40)
    source_reference: str | None = Field(default=None, max_length=255)

    @field_validator("character", "pinyin")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value

    @field_validator("radical", "simple_meaning", "example_sentence", "source_reference")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("common_words", "tags")
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        return normalize_list(value)


class CharacterUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character: str | None = Field(default=None, min_length=1, max_length=1)
    pinyin: str | None = Field(default=None, min_length=1, max_length=120)
    stroke_count: int | None = Field(default=None, ge=1, le=100)
    radical: str | None = Field(default=None, max_length=16)
    frequency_rank: int | None = Field(default=None, ge=1)
    difficulty_level: int | None = Field(default=None, ge=1, le=10)
    simple_meaning: str | None = None
    example_sentence: str | None = None
    common_words: list[str] | None = Field(default=None, max_length=30)
    tags: list[str] | None = Field(default=None, max_length=30)
    is_enabled: bool | None = None
    status: str | None = Field(default=None, pattern="^(active|archived)$")

    @field_validator("character", "pinyin")
    @classmethod
    def strip_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value

    @field_validator("radical", "simple_meaning", "example_sentence")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("common_words", "tags")
    @classmethod
    def clean_lists(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else normalize_list(value)


class CharacterResponse(BaseModel):
    id: uuid.UUID
    character: str
    pinyin: str
    stroke_count: int | None
    radical: str | None
    frequency_rank: int | None
    difficulty_level: int | None
    simple_meaning: str | None
    example_sentence: str | None
    common_words: list[str]
    tags: list[str]
    is_enabled: bool
    status: str
    source_type: str
    source_reference: str | None
    created_at: datetime
    updated_at: datetime


class CharacterPage(BaseModel):
    items: list[CharacterResponse]
    page: int
    page_size: int
    total: int
    pages: int


class BulkCharacterImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^1\.\d+$")
    items: list[CharacterCreate] = Field(min_length=1, max_length=1000)


class ImportReport(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class AdminOverviewResponse(BaseModel):
    users: int
    families: int
    children: int
    characters: int


class KnowledgeRelationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: str = Field(pattern="^(related|prerequisite|confusing|derived)$")


class KnowledgeRelationResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: str
    created_at: datetime
    updated_at: datetime
