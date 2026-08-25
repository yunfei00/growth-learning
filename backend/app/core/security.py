"""Password hashing and short-lived signed browser session tokens."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import Settings

_password_hash = PasswordHash.recommended()
_algorithm = "HS256"


class AuthenticationTokenError(ValueError):
    """Raised when a browser session token is absent, invalid, or expired."""


@dataclass(frozen=True)
class BrowserSessionClaims:
    user_id: uuid.UUID
    session_version: int


def hash_password(password: str) -> str:
    """Hash a password with pwdlib's recommended Argon2 configuration."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password without exposing hash details to callers."""
    return _password_hash.verify(password, password_hash)


def create_session_token(user_id: uuid.UUID, settings: Settings, session_version: int = 0) -> str:
    """Create an expiring signed token for the HttpOnly session cookie."""
    issued_at = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "browser_session",
        "iss": settings.auth_token_issuer,
        "ver": session_version,
        "iat": issued_at,
        "exp": issued_at + timedelta(seconds=settings.auth_token_ttl_seconds),
    }
    return jwt.encode(payload, settings.auth_secret.get_secret_value(), algorithm=_algorithm)


def read_session_claims(token: str, settings: Settings) -> BrowserSessionClaims:
    """Validate a signed browser session and return identity plus revocation version."""
    try:
        payload = jwt.decode(
            token,
            settings.auth_secret.get_secret_value(),
            algorithms=[_algorithm],
            issuer=settings.auth_token_issuer,
        )
        if payload.get("type") != "browser_session":
            raise AuthenticationTokenError
        version = payload.get("ver", 0)
        if not isinstance(version, int) or version < 0:
            raise AuthenticationTokenError
        return BrowserSessionClaims(uuid.UUID(payload["sub"]), version)
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise AuthenticationTokenError from error


def read_session_user_id(token: str, settings: Settings) -> uuid.UUID:
    """Compatibility wrapper for callers that only need the user identifier."""
    return read_session_claims(token, settings).user_id
