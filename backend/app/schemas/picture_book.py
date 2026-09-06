"""Contracts for legal open-library picture books and private imported pages."""

import uuid

from pydantic import BaseModel, Field


class OpenPictureBookSummary(BaseModel):
    source_provider: str = "gdl"
    source_book_id: str
    title: str
    description: str
    reading_level: str
    license_name: str
    source_url: str
    thumbnail_url: str | None = None
    publisher: str | None = None
    authors: list[str] = Field(default_factory=list)


class OpenPictureBookPage(BaseModel):
    position: int
    text: str
    image_available: bool
    image_alt: str | None = None
    pinyin: list[str | None]


class PictureBookDetail(BaseModel):
    id: uuid.UUID
    story_version_id: uuid.UUID
    title: str
    source_provider: str
    source_book_id: str
    source_url: str
    license_name: str
    reading_level: str
    attribution: dict[str, object]
    pages: list[OpenPictureBookPage]


class PictureBookImportResponse(BaseModel):
    picture_book_id: uuid.UUID
    story_version_id: uuid.UUID
    imported: bool
    audio_prepared: bool
