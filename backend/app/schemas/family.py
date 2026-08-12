"""Public schemas for family membership and child profiles."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FamilyRoleValue = Literal["admin", "companion"]
GenderValue = Literal["male", "female", "other"]


def _strip_required_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Name cannot be blank")
    return value


class FamilyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    _normalize_name = field_validator("name")(_strip_required_name)


class FamilyUpdate(FamilyCreate):
    """Phase 2 supports renaming a family as its only mutable setting."""


class FamilyResponse(BaseModel):
    id: uuid.UUID
    name: str
    current_role: FamilyRoleValue
    created_at: datetime
    updated_at: datetime


class MemberUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str


class FamilyMemberResponse(BaseModel):
    id: uuid.UUID
    role: FamilyRoleValue
    user: MemberUserResponse
    created_at: datetime
    updated_at: datetime


class ChildCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=80)
    nickname: str | None = Field(default=None, max_length=80)
    birth_date: date
    gender: GenderValue | None = None
    avatar_key: str | None = Field(default=None, max_length=255)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return _strip_required_name(value)

    @field_validator("nickname", "avatar_key")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("birth_date")
    @classmethod
    def reject_future_birth_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Birth date cannot be in the future")
        return value


class ChildUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    nickname: str | None = Field(default=None, max_length=80)
    birth_date: date | None = None
    gender: GenderValue | None = None
    avatar_key: str | None = Field(default=None, max_length=255)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Display name cannot be null")
        return _strip_required_name(value)

    @field_validator("nickname", "avatar_key")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("birth_date")
    @classmethod
    def reject_invalid_birth_date(cls, value: date | None) -> date | None:
        if value is None:
            raise ValueError("Birth date cannot be null")
        if value > date.today():
            raise ValueError("Birth date cannot be in the future")
        return value


class ChildResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    family_id: uuid.UUID
    display_name: str
    nickname: str | None
    birth_date: date
    gender: GenderValue | None
    avatar_key: str | None
    created_at: datetime
    updated_at: datetime
