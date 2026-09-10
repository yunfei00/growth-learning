"""Contracts for legal open-library picture books and private imported pages."""

import uuid

from pydantic import BaseModel, Field, field_validator


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


class FamilyPictureBookUpdateRequest(BaseModel):
    """Editable fields for a household-private uploaded picture book."""

    title: str = Field(min_length=1, max_length=120)
    page_texts: list[str] = Field(min_length=1, max_length=24)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("请填写绘本标题")
        return cleaned

    @field_validator("page_texts")
    @classmethod
    def clean_page_texts(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("每一页都需要填写文字")
        if any(len(value) > 220 for value in cleaned):
            raise ValueError("单页文字不能超过 220 个字符")
        return cleaned
