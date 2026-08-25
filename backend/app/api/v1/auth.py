"""Invite-only account registration and revocable browser-cookie authentication."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.core.security import create_session_token, hash_password, verify_password
from app.models import AccountStatus, User
from app.schemas.auth import (
    AccountStatusResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.auth_rate_limit import enforce_auth_rate_limit
from app.services.platform_access import (
    EmailAlreadyRegisteredError,
    InvitationUnavailableError,
    RegistrationUnavailableError,
    add_platform_audit,
    register_platform_user,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _set_session_cookie(response: Response, request: Request, user: User) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=create_session_token(user.id, settings, user.session_version),
        max_age=settings.auth_token_ttl_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path=settings.auth_cookie_path,
    )


def _delete_session_cookie(response: Response, request: Request) -> None:
    settings = request.app.state.settings
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path=settings.auth_cookie_path,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, session: DbSession) -> User:
    """Atomically create an active account through the configured admission policy."""
    settings = request.app.state.settings
    await enforce_auth_rate_limit(
        request,
        scope="register",
        identifier="all",
        limit=settings.auth_registration_rate_limit,
    )
    try:
        return await register_platform_user(
            session,
            settings,
            invitation_code=payload.invitation_code,
            email=str(payload.email),
            display_name=payload.display_name,
            password=payload.password,
        )
    except RegistrationUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前不开放账号注册",
        ) from error
    except InvitationUnavailableError as error:
        detail = (
            "邀请码已过期，请联系邀请人获取新的邀请码。"
            if error.reason == "expired"
            else "邀请码无效或已不可使用"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from error
    except EmailAlreadyRegisteredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该邮箱已经注册，请直接登录。",
        ) from error


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest, request: Request, response: Response, session: DbSession
) -> User:
    """Authenticate with a generic failure response and set an HttpOnly cookie."""
    settings = request.app.state.settings
    await enforce_auth_rate_limit(
        request,
        scope="login",
        identifier="all",
        limit=settings.auth_login_rate_limit,
    )
    user = await session.scalar(select(User).where(User.email == str(payload.email)))
    password_is_valid = user is not None and verify_password(payload.password, user.password_hash)
    if user is None or user.account_status != AccountStatus.ACTIVE or not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    _set_session_cookie(response, request, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> None:
    """Expire the browser session cookie using the same configured path."""
    _delete_session_cookie(response, request)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> User:
    """Return the authenticated adult without credential fields."""
    return current_user


@router.get("/account", response_model=AccountStatusResponse)
async def account(current_user: CurrentUser) -> User:
    """Return self-service account metadata without household data."""
    return current_user


@router.post("/change-password", response_model=UserResponse)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    current_user: CurrentUser,
    session: DbSession,
) -> User:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    current_user.password_hash = hash_password(payload.new_password)
    current_user.session_version += 1
    add_platform_audit(
        session,
        event_type="user_changed_password",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
    )
    await session.commit()
    await session.refresh(current_user)
    _set_session_cookie(response, request, current_user)
    return current_user


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all_devices(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    session: DbSession,
) -> None:
    current_user.session_version += 1
    add_platform_audit(
        session,
        event_type="user_logged_out_all_sessions",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
    )
    await session.commit()
    _delete_session_cookie(response, request)
