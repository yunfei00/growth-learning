"""Shared authentication dependencies for protected API routes."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthenticationTokenError, read_session_claims
from app.db.session import get_db_session
from app.models import AccountStatus, SystemRole, User

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(request: Request, session: DbSession) -> User:
    """Resolve the active user from the configured HttpOnly cookie."""
    settings = request.app.state.settings
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        claims = read_session_claims(token, settings)
    except AuthenticationTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        ) from error

    user = await session.get(User, claims.user_id)
    if (
        user is None
        or user.account_status != AccountStatus.ACTIVE
        or user.session_version != claims.session_version
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_system_admin(current_user: CurrentUser) -> User:
    """Permit system administration without granting household membership."""
    if current_user.system_role != SystemRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System administrator permission required",
        )
    return current_user


SystemAdmin = Annotated[User, Depends(require_system_admin)]
