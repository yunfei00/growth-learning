"""Server-side system administrator provisioning operations."""

from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import AccountStatus, RegistrationSource, SystemRole, User
from app.services.platform_access import add_platform_audit


@dataclass(frozen=True)
class ProvisionResult:
    user: User
    action: str


def normalize_email(email: str) -> str:
    try:
        normalized = validate_email(email.strip(), check_deliverability=False).normalized
    except EmailNotValidError as error:
        raise ValueError("A valid administrator email is required") from error
    return normalized.casefold()


async def create_admin(
    session: AsyncSession, *, email: str, display_name: str, password: str
) -> ProvisionResult:
    """Create an admin once; existing accounts require explicit promotion."""
    normalized_email = normalize_email(email)
    existing = await session.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        action = "already_admin" if existing.system_role == SystemRole.ADMIN else "existing_user"
        return ProvisionResult(existing, action)

    normalized_name = display_name.strip()
    if not normalized_name:
        raise ValueError("Administrator display name is required")
    user = User(
        email=normalized_email,
        display_name=normalized_name,
        password_hash=hash_password(password),
        system_role=SystemRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
        is_active=True,
        registration_source=RegistrationSource.ADMIN_CREATED,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return ProvisionResult(user, "created")


async def promote_admin(session: AsyncSession, *, email: str) -> ProvisionResult:
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        raise LookupError("User not found")
    if user.system_role == SystemRole.ADMIN:
        return ProvisionResult(user, "already_admin")
    user.system_role = SystemRole.ADMIN
    await session.commit()
    await session.refresh(user)
    return ProvisionResult(user, "promoted")


async def set_admin_password(
    session: AsyncSession, *, email: str, password: str
) -> ProvisionResult:
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or user.system_role != SystemRole.ADMIN:
        raise LookupError("System administrator not found")
    user.password_hash = hash_password(password)
    user.session_version += 1
    add_platform_audit(
        session,
        event_type="admin_reset_password",
        actor_user_id=None,
        target_user_id=user.id,
        metadata={"source": "server_cli"},
    )
    await session.commit()
    await session.refresh(user)
    return ProvisionResult(user, "password_updated")


async def reset_user_password(
    session: AsyncSession, *, email: str, password: str
) -> ProvisionResult:
    """Server recovery path for any account; the password is read outside argv."""
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        raise LookupError("User not found")
    user.password_hash = hash_password(password)
    user.session_version += 1
    add_platform_audit(
        session,
        event_type="admin_reset_password",
        actor_user_id=None,
        target_user_id=user.id,
        metadata={"source": "server_cli"},
    )
    await session.commit()
    await session.refresh(user)
    return ProvisionResult(user, "password_reset")
