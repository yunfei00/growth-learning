"""System-administrator account and invitation management schemas."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    account_status: str
    system_role: str
    registration_source: str
    registered_via_invitation_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None
    family_count: int


class AdminUserPage(BaseModel):
    items: list[AdminUserResponse]
    page: int
    page_size: int
    total: int
    pages: int


class AdminUserStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_status: Literal["active", "suspended", "disabled"]


class InvitationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: Literal["create_account"] = "create_account"
    expires_at: datetime
    max_uses: int = Field(default=1, ge=1, le=100)
    email_constraint: EmailStr | None = None

    @field_validator("expires_at")
    @classmethod
    def expiry_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        return value.astimezone(UTC)


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purpose: str
    status: str
    code_hint: str
    created_by_user_id: uuid.UUID
    created_by_display_name: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    max_uses: int
    used_count: int
    email_constraint: EmailStr | None
    revoked_at: datetime | None
    last_used_at: datetime | None


class InvitationCreatedResponse(InvitationResponse):
    invitation_code: str


class InvitationPage(BaseModel):
    items: list[InvitationResponse]
    page: int
    page_size: int
    total: int
    pages: int
