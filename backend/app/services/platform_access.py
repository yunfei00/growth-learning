"""Invite-only admission, account lifecycle, and append-only platform audit operations."""

import base64
import hashlib
import hmac
import math
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import hash_password
from app.models import (
    AccountStatus,
    FamilyMember,
    InvitationStoredStatus,
    PlatformAuditLog,
    PlatformInvitation,
    RegistrationSource,
    User,
)


class RegistrationUnavailableError(ValueError):
    """Raised when platform configuration does not admit public account creation."""


class InvitationUnavailableError(ValueError):
    """Raised with a deliberately small set of safe public failure reasons."""

    def __init__(self, reason: str = "invalid") -> None:
        super().__init__(reason)
        self.reason = reason


class EmailAlreadyRegisteredError(ValueError):
    """Raised when the normalized email already belongs to a platform account."""


@dataclass(frozen=True)
class InvitationCreationResult:
    invitation: PlatformInvitation
    plaintext_code: str


@dataclass(frozen=True)
class AdminUserRow:
    user: User
    family_count: int


@dataclass(frozen=True)
class AdminUserPageResult:
    items: list[AdminUserRow]
    page: int
    page_size: int
    total: int
    pages: int


def utc_now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def normalize_invitation_code(code: str) -> str:
    return code.strip().upper()


def hash_invitation_code(code: str, settings: Settings) -> str:
    """Return a keyed digest so the database never contains reusable invitation secrets."""
    return hmac.new(
        settings.effective_invitation_code_secret.encode(),
        normalize_invitation_code(code).encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_invitation_code() -> str:
    """Generate a non-guessable, human-copyable code with 120 random bits."""
    encoded = base64.b32encode(secrets.token_bytes(15)).decode().rstrip("=")
    return f"GL-{encoded}"


def invitation_code_hint(code: str) -> str:
    normalized = normalize_invitation_code(code)
    return f"{normalized[:7]}-••••"


def normalize_optional_email_constraint(email: str | None) -> str | None:
    if not email:
        return None
    try:
        normalized = validate_email(email.strip(), check_deliverability=False).normalized
    except EmailNotValidError as error:
        raise ValueError("A valid invitation email constraint is required") from error
    return normalized.casefold()


def effective_invitation_status(invitation: PlatformInvitation, now: datetime | None = None) -> str:
    current = now or utc_now()
    if invitation.status == InvitationStoredStatus.REVOKED or invitation.revoked_at is not None:
        return "revoked"
    if _aware(invitation.expires_at) <= current:
        return "expired"
    if invitation.used_count >= invitation.max_uses:
        return "used" if invitation.max_uses == 1 else "exhausted"
    return "active"


def add_platform_audit(
    session: AsyncSession,
    *,
    event_type: str,
    actor_user_id: uuid.UUID | None,
    target_user_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> None:
    """Stage an audit event; callers commit it with the protected business operation."""
    session.add(
        PlatformAuditLog(
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            event_type=event_type,
            metadata_json=metadata or {},
        )
    )


async def create_platform_invitation(
    session: AsyncSession,
    settings: Settings,
    *,
    actor: User,
    expires_at: datetime,
    max_uses: int,
    email_constraint: str | None,
) -> InvitationCreationResult:
    if _aware(expires_at) <= utc_now():
        raise ValueError("Invitation expiry must be in the future")
    if max_uses < 1 or max_uses > 100:
        raise ValueError("Invitation max uses must be between 1 and 100")
    code = generate_invitation_code()
    invitation = PlatformInvitation(
        code_hash=hash_invitation_code(code, settings),
        code_hint=invitation_code_hint(code),
        created_by_user_id=actor.id,
        expires_at=_aware(expires_at),
        max_uses=max_uses,
        email_constraint=normalize_optional_email_constraint(email_constraint),
    )
    session.add(invitation)
    await session.flush()
    add_platform_audit(
        session,
        event_type="admin_created_invitation",
        actor_user_id=actor.id,
        metadata={
            "invitation_id": str(invitation.id),
            "purpose": invitation.purpose,
            "max_uses": max_uses,
            "email_constrained": bool(invitation.email_constraint),
        },
    )
    await session.commit()
    await session.refresh(invitation)
    return InvitationCreationResult(invitation, code)


async def revoke_platform_invitation(
    session: AsyncSession, *, invitation_id: uuid.UUID, actor: User
) -> PlatformInvitation | None:
    invitation = await session.scalar(
        select(PlatformInvitation).where(PlatformInvitation.id == invitation_id).with_for_update()
    )
    if invitation is None:
        return None
    if effective_invitation_status(invitation) == "active":
        invitation.status = InvitationStoredStatus.REVOKED
        invitation.revoked_at = utc_now()
        add_platform_audit(
            session,
            event_type="admin_revoked_invitation",
            actor_user_id=actor.id,
            metadata={"invitation_id": str(invitation.id)},
        )
        await session.commit()
        await session.refresh(invitation)
    return invitation


async def register_platform_user(
    session: AsyncSession,
    settings: Settings,
    *,
    invitation_code: str | None,
    email: str,
    display_name: str,
    password: str,
) -> User:
    """Create a user and consume an invitation in one row-locked transaction."""
    if settings.registration_mode in {"closed", "approval"}:
        raise RegistrationUnavailableError

    invitation: PlatformInvitation | None = None
    if settings.registration_mode == "invite_only":
        if not invitation_code:
            raise InvitationUnavailableError
        invitation = await session.scalar(
            select(PlatformInvitation)
            .where(PlatformInvitation.code_hash == hash_invitation_code(invitation_code, settings))
            .with_for_update()
        )
        if invitation is None:
            raise InvitationUnavailableError
        invitation_status = effective_invitation_status(invitation)
        if invitation_status == "expired":
            raise InvitationUnavailableError("expired")
        if invitation_status != "active":
            raise InvitationUnavailableError
        if invitation.purpose != "create_account":
            raise InvitationUnavailableError
        if invitation.email_constraint and invitation.email_constraint != email:
            raise InvitationUnavailableError

    if await session.scalar(select(User.id).where(User.email == email)) is not None:
        raise EmailAlreadyRegisteredError

    user = User(
        email=email,
        display_name=display_name,
        password_hash=hash_password(password),
        is_active=True,
        account_status=AccountStatus.ACTIVE,
        registration_source=(
            RegistrationSource.PLATFORM_INVITATION
            if invitation is not None
            else RegistrationSource.LEGACY
        ),
        registered_via_invitation_id=invitation.id if invitation is not None else None,
    )
    session.add(user)
    try:
        await session.flush()
        if invitation is not None:
            invitation.used_count += 1
            invitation.last_used_at = utc_now()
            if invitation.used_count >= invitation.max_uses:
                invitation.status = InvitationStoredStatus.EXHAUSTED
        add_platform_audit(
            session,
            event_type="user_registered",
            actor_user_id=user.id,
            target_user_id=user.id,
            metadata={
                "registration_source": user.registration_source,
                "invitation_id": str(invitation.id) if invitation is not None else None,
            },
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise EmailAlreadyRegisteredError from error
    await session.refresh(user)
    return user


async def list_admin_users(
    session: AsyncSession,
    *,
    search: str | None,
    account_status: str | None,
    page: int,
    page_size: int,
) -> AdminUserPageResult:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(User.display_name.ilike(term), User.email.ilike(term)))
    if account_status:
        filters.append(User.account_status == account_status)

    total = int(await session.scalar(select(func.count()).select_from(User).where(*filters)) or 0)
    family_count = func.count(FamilyMember.id).label("family_count")
    rows = (
        await session.execute(
            select(User, family_count)
            .outerjoin(FamilyMember, FamilyMember.user_id == User.id)
            .where(*filters)
            .group_by(User.id)
            .order_by(User.created_at.desc(), User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return AdminUserPageResult(
        items=[AdminUserRow(user=row[0], family_count=int(row[1])) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def set_user_account_status(
    session: AsyncSession,
    *,
    target: User,
    new_status: str,
    actor_user_id: uuid.UUID | None,
) -> User:
    old_status = target.account_status
    if old_status == new_status:
        return target
    target.account_status = new_status
    target.is_active = new_status == AccountStatus.ACTIVE
    target.session_version += 1
    event = {
        AccountStatus.SUSPENDED: "admin_suspended_user",
        AccountStatus.ACTIVE: "admin_reactivated_user",
        AccountStatus.DISABLED: "admin_disabled_user",
    }[new_status]
    add_platform_audit(
        session,
        event_type=event,
        actor_user_id=actor_user_id,
        target_user_id=target.id,
        metadata={"old_status": old_status, "new_status": new_status},
    )
    await session.commit()
    await session.refresh(target)
    return target
