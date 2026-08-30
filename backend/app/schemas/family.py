"""Public schemas for family membership and child profiles."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

FamilyRoleValue = Literal["admin", "companion"]
GenderValue = Literal["male", "female", "other"]
AdultChildRelationValue = Literal[
    "father", "mother", "grandfather", "grandmother", "guardian", "other"
]


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


class AdultChildRelationResponse(BaseModel):
    id: uuid.UUID
    child_id: uuid.UUID
    relation: AdultChildRelationValue
    created_at: datetime
    updated_at: datetime


class FamilyMemberResponse(BaseModel):
    id: uuid.UUID
    role: FamilyRoleValue
    user: MemberUserResponse
    relations: list[AdultChildRelationResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FamilyMemberRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: FamilyRoleValue


class AdultChildRelationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: AdultChildRelationValue


class FamilyInvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_constraint: EmailStr | None = None
    role_to_grant: FamilyRoleValue = "companion"
    expires_at: datetime


class FamilyInvitationResponse(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    family_name: str
    code_hint: str
    status: Literal["active", "expired", "revoked", "used"]
    role_to_grant: FamilyRoleValue
    email_constraint: str | None
    created_by_user_id: uuid.UUID
    created_by_display_name: str
    expires_at: datetime
    used_count: int
    revoked_at: datetime | None
    accepted_by_user_id: uuid.UUID | None
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FamilyInvitationCreatedResponse(FamilyInvitationResponse):
    invitation_code: str


class FamilyInvitationAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invitation_code: str = Field(min_length=8, max_length=80)


class FamilyInvitationAcceptResponse(BaseModel):
    family_id: uuid.UUID
    family_name: str
    membership_id: uuid.UUID
    role: FamilyRoleValue
    already_member: bool


class FamilyActivityResponse(BaseModel):
    id: uuid.UUID
    kind: Literal["learning", "reading", "science", "growth"]
    child_id: uuid.UUID
    child_name: str
    actor_user_id: uuid.UUID | None
    actor_display_name: str | None
    title: str
    occurred_at: datetime


class ChildCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=80)
    nickname: str | None = Field(default=None, max_length=80)
    birth_date: date
    gender: GenderValue | None = None
    avatar_key: str | None = Field(default=None, max_length=255)
    current_grade_level: int | None = Field(default=None, ge=1, le=9)
    school_year: str | None = Field(default=None, pattern=r"^\d{4}-\d{4}$")

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
    current_grade_level: int | None = Field(default=None, ge=1, le=9)
    school_year: str | None = Field(default=None, pattern=r"^\d{4}-\d{4}$")

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
    current_grade_level: int | None
    school_year: str | None
    is_archived: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
