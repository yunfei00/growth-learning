"""Server-side system administrator provisioning operations."""

from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import SystemRole, User


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
    await session.commit()
    await session.refresh(user)
    return ProvisionResult(user, "password_updated")
