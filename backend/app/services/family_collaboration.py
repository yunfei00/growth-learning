"""Household invitations, member administration, and relationship labels."""

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    AdultChildRelation,
    Child,
    Family,
    FamilyInvitation,
    FamilyMember,
    FamilyRole,
    User,
)
from app.services.platform_access import add_platform_audit


class FamilyInvitationUnavailableError(ValueError):
    """A safe, finite failure reason for a household invitation."""

    def __init__(self, reason: str = "invalid") -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class FamilyInvitationCreationResult:
    invitation: FamilyInvitation
    plaintext_code: str


@dataclass(frozen=True)
class FamilyInvitationAcceptanceResult:
    invitation: FamilyInvitation
    family: Family
    membership: FamilyMember
    already_member: bool


def utc_now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def normalize_family_invitation_code(code: str) -> str:
    return code.strip().upper()


def hash_family_invitation_code(code: str, settings: Settings) -> str:
    """Domain-separate family joins from platform registration invitation hashes."""
    message = f"family-invitation-v1:{normalize_family_invitation_code(code)}"
    return hmac.new(
        settings.effective_invitation_code_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_family_invitation_code() -> str:
    encoded = base64.b32encode(secrets.token_bytes(15)).decode().rstrip("=")
    return f"GLF-{encoded}"


def family_invitation_code_hint(code: str) -> str:
    normalized = normalize_family_invitation_code(code)
    return f"{normalized[:8]}-••••"


def normalize_family_email_constraint(email: str | None) -> str | None:
    if not email:
        return None
    try:
        normalized = validate_email(email.strip(), check_deliverability=False).normalized
    except EmailNotValidError as error:
        raise ValueError("A valid family invitation email is required") from error
    return normalized.casefold()


def effective_family_invitation_status(
    invitation: FamilyInvitation, now: datetime | None = None
) -> str:
    current = now or utc_now()
    if invitation.revoked_at is not None:
        return "revoked"
    if invitation.accepted_by_user_id is not None or invitation.used_count >= invitation.max_uses:
        return "used"
    if _aware(invitation.expires_at) <= current:
        return "expired"
    return "active"


async def create_family_invitation(
    session: AsyncSession,
    settings: Settings,
    *,
    family: Family,
    actor: User,
    role_to_grant: str,
    email_constraint: str | None,
    expires_at: datetime,
) -> FamilyInvitationCreationResult:
    if role_to_grant not in {FamilyRole.ADMIN, FamilyRole.COMPANION}:
        raise ValueError("Unsupported family role")
    if _aware(expires_at) <= utc_now():
        raise ValueError("Family invitation expiry must be in the future")
    code = generate_family_invitation_code()
    invitation = FamilyInvitation(
        family_id=family.id,
        code_hash=hash_family_invitation_code(code, settings),
        code_hint=family_invitation_code_hint(code),
        created_by_user_id=actor.id,
        role_to_grant=role_to_grant,
        email_constraint=normalize_family_email_constraint(email_constraint),
        expires_at=_aware(expires_at),
        max_uses=1,
    )
    session.add(invitation)
    await session.flush()
    add_platform_audit(
        session,
        event_type="family_invitation_created",
        actor_user_id=actor.id,
        metadata={
            "family_id": str(family.id),
            "invitation_id": str(invitation.id),
            "role_to_grant": role_to_grant,
            "email_constrained": bool(invitation.email_constraint),
        },
    )
    await session.commit()
    await session.refresh(invitation)
    return FamilyInvitationCreationResult(invitation, code)


async def revoke_family_invitation(
    session: AsyncSession,
    *,
    family_id: uuid.UUID,
    invitation_id: uuid.UUID,
    actor: User,
) -> FamilyInvitation | None:
    invitation = await session.scalar(
        select(FamilyInvitation)
        .where(
            FamilyInvitation.id == invitation_id,
            FamilyInvitation.family_id == family_id,
        )
        .with_for_update()
    )
    if invitation is None:
        return None
    if effective_family_invitation_status(invitation) == "active":
        invitation.revoked_at = utc_now()
        add_platform_audit(
            session,
            event_type="family_invitation_revoked",
            actor_user_id=actor.id,
            metadata={"family_id": str(family_id), "invitation_id": str(invitation.id)},
        )
        await session.commit()
        await session.refresh(invitation)
    return invitation


async def _accept_locked_invitation(
    session: AsyncSession,
    *,
    invitation: FamilyInvitation | None,
    current_user: User,
) -> FamilyInvitationAcceptanceResult:
    if invitation is None:
        raise FamilyInvitationUnavailableError
    family = await session.scalar(
        select(Family).where(Family.id == invitation.family_id).with_for_update()
    )
    if family is None:
        raise FamilyInvitationUnavailableError

    membership = await session.scalar(
        select(FamilyMember).where(
            FamilyMember.family_id == family.id,
            FamilyMember.user_id == current_user.id,
        )
    )
    if (
        invitation.accepted_by_user_id == current_user.id
        and invitation.used_count == 1
        and membership is not None
    ):
        return FamilyInvitationAcceptanceResult(invitation, family, membership, True)

    invitation_status = effective_family_invitation_status(invitation)
    if invitation_status != "active":
        raise FamilyInvitationUnavailableError(invitation_status)
    if invitation.email_constraint and invitation.email_constraint != current_user.email:
        raise FamilyInvitationUnavailableError("wrong_email")

    already_member = membership is not None
    if membership is None:
        membership = FamilyMember(
            family_id=family.id,
            user_id=current_user.id,
            role=invitation.role_to_grant,
        )
        session.add(membership)
        await session.flush()
    invitation.used_count = 1
    invitation.accepted_by_user_id = current_user.id
    invitation.accepted_at = utc_now()
    add_platform_audit(
        session,
        event_type="family_invitation_accepted",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        metadata={
            "family_id": str(family.id),
            "invitation_id": str(invitation.id),
            "membership_id": str(membership.id),
            "already_member": already_member,
        },
    )
    await session.commit()
    await session.refresh(invitation)
    await session.refresh(membership)
    return FamilyInvitationAcceptanceResult(invitation, family, membership, already_member)


async def accept_family_invitation_code(
    session: AsyncSession,
    settings: Settings,
    *,
    invitation_code: str,
    current_user: User,
) -> FamilyInvitationAcceptanceResult:
    invitation = await session.scalar(
        select(FamilyInvitation)
        .where(
            FamilyInvitation.code_hash
            == hash_family_invitation_code(invitation_code, settings)
        )
        .with_for_update()
    )
    return await _accept_locked_invitation(
        session, invitation=invitation, current_user=current_user
    )


async def accept_email_bound_family_invitation(
    session: AsyncSession,
    *,
    invitation_id: uuid.UUID,
    current_user: User,
) -> FamilyInvitationAcceptanceResult:
    invitation = await session.scalar(
        select(FamilyInvitation)
        .where(
            FamilyInvitation.id == invitation_id,
            FamilyInvitation.email_constraint == current_user.email,
        )
        .with_for_update()
    )
    return await _accept_locked_invitation(
        session, invitation=invitation, current_user=current_user
    )


async def update_family_member_role(
    session: AsyncSession,
    *,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    role: str,
    actor: User,
) -> FamilyMember | None:
    members = list(
        (
            await session.scalars(
                select(FamilyMember)
                .where(FamilyMember.family_id == family_id)
                .with_for_update()
            )
        ).all()
    )
    target = next((member for member in members if member.id == member_id), None)
    if target is None:
        return None
    if target.role == role:
        return target
    if target.role == FamilyRole.ADMIN and role != FamilyRole.ADMIN:
        admin_count = sum(member.role == FamilyRole.ADMIN for member in members)
        if admin_count <= 1:
            raise ValueError("A family must keep at least one administrator")
    target.role = role
    add_platform_audit(
        session,
        event_type="family_member_role_updated",
        actor_user_id=actor.id,
        target_user_id=target.user_id,
        metadata={"family_id": str(family_id), "membership_id": str(target.id), "role": role},
    )
    await session.commit()
    await session.refresh(target)
    return target


async def remove_family_member(
    session: AsyncSession,
    *,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    actor: User,
) -> bool:
    members = list(
        (
            await session.scalars(
                select(FamilyMember)
                .where(FamilyMember.family_id == family_id)
                .with_for_update()
            )
        ).all()
    )
    target = next((member for member in members if member.id == member_id), None)
    if target is None:
        return False
    if target.role == FamilyRole.ADMIN:
        admin_count = sum(member.role == FamilyRole.ADMIN for member in members)
        if admin_count <= 1:
            raise ValueError("A family must keep at least one administrator")
    await session.execute(
        delete(AdultChildRelation).where(
            AdultChildRelation.family_id == family_id,
            AdultChildRelation.user_id == target.user_id,
        )
    )
    target_user_id = target.user_id
    await session.delete(target)
    add_platform_audit(
        session,
        event_type="family_member_removed",
        actor_user_id=actor.id,
        target_user_id=target_user_id,
        metadata={"family_id": str(family_id), "membership_id": str(member_id)},
    )
    await session.commit()
    return True


async def set_adult_child_relation(
    session: AsyncSession,
    *,
    family_id: uuid.UUID,
    member_id: uuid.UUID,
    child_id: uuid.UUID,
    relation: str,
    actor: User,
) -> AdultChildRelation | None:
    member = await session.scalar(
        select(FamilyMember).where(
            FamilyMember.id == member_id,
            FamilyMember.family_id == family_id,
        )
    )
    child = await session.scalar(
        select(Child).where(Child.id == child_id, Child.family_id == family_id)
    )
    if member is None or child is None:
        return None
    current = await session.scalar(
        select(AdultChildRelation).where(
            AdultChildRelation.user_id == member.user_id,
            AdultChildRelation.child_id == child.id,
        )
    )
    if current is None:
        current = AdultChildRelation(
            family_id=family_id,
            user_id=member.user_id,
            child_id=child.id,
            relation=relation,
        )
        session.add(current)
    else:
        current.relation = relation
    add_platform_audit(
        session,
        event_type="adult_child_relation_updated",
        actor_user_id=actor.id,
        target_user_id=member.user_id,
        metadata={
            "family_id": str(family_id),
            "child_id": str(child.id),
            "relation": relation,
        },
    )
    await session.commit()
    await session.refresh(current)
    return current
