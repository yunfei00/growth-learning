"""Phase 14 platform admission, account lifecycle, and session revocation tests."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import verify_password
from app.models import (
    AccountStatus,
    PlatformAuditLog,
    PlatformInvitation,
    RegistrationSource,
    SystemRole,
    User,
)

pytestmark = pytest.mark.anyio

PASSWORD = "phase14-secure-password"
NEW_PASSWORD = "phase14-new-secure-password"


async def register_open(client: httpx.AsyncClient, email: str, name: str = "测试家长") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": name, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> dict:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


async def make_admin(session_factory: async_sessionmaker[AsyncSession], user_id: str) -> None:
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(user_id))
        assert user is not None
        user.system_role = SystemRole.ADMIN
        await session.commit()


async def create_admin_and_login(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    email: str = "platform-admin@example.com",
) -> dict:
    user = await register_open(client, email, "平台管理员")
    await make_admin(session_factory, user["id"])
    await login(client, email)
    return user


async def create_invitation(
    admin: httpx.AsyncClient,
    *,
    max_uses: int = 1,
    email: str | None = None,
    days: int = 7,
) -> dict:
    response = await admin.post(
        "/api/v1/admin/invitations",
        json={
            "purpose": "create_account",
            "expires_at": (datetime.now(UTC) + timedelta(days=days)).isoformat(),
            "max_uses": max_uses,
            "email_constraint": email,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def invite_registration_payload(code: str | None, email: str) -> dict:
    return {
        "invitation_code": code,
        "email": email,
        "display_name": "受邀家长",
        "password": PASSWORD,
    }


async def test_invite_only_rejects_missing_fake_and_closed_registration(
    client: httpx.AsyncClient, test_app: FastAPI
) -> None:
    test_app.state.settings.registration_mode = "invite_only"
    missing = await client.post(
        "/api/v1/auth/register",
        json=invite_registration_payload(None, "missing@example.com"),
    )
    fake = await client.post(
        "/api/v1/auth/register",
        json=invite_registration_payload("GL-FAKE-NOT-A-REAL-CODE", "fake@example.com"),
    )
    assert missing.status_code == 400
    assert fake.status_code == 400
    assert missing.json()["detail"] == "邀请码无效或已不可使用"
    assert fake.json()["detail"] == "邀请码无效或已不可使用"

    test_app.state.settings.registration_mode = "closed"
    closed = await client.post(
        "/api/v1/auth/register",
        json=invite_registration_payload("GL-ANYTHING", "closed@example.com"),
    )
    assert closed.status_code == 403


async def test_expired_and_revoked_invitations_are_rejected(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as admin:
        await create_admin_and_login(admin, session_factory)
        expired = await create_invitation(admin)
        revoked = await create_invitation(admin)
        async with session_factory() as session:
            invitation = await session.get(PlatformInvitation, uuid.UUID(expired["id"]))
            assert invitation is not None
            invitation.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()
        revoke = await admin.post(f"/api/v1/admin/invitations/{revoked['id']}/revoke")
        assert revoke.status_code == 200
        assert revoke.json()["status"] == "revoked"

        test_app.state.settings.registration_mode = "invite_only"
        expired_result = await admin.post(
            "/api/v1/auth/register",
            json=invite_registration_payload(expired["invitation_code"], "expired@example.com"),
        )
        revoked_result = await admin.post(
            "/api/v1/auth/register",
            json=invite_registration_payload(revoked["invitation_code"], "revoked@example.com"),
        )
        assert expired_result.status_code == 400
        assert "已过期" in expired_result.json()["detail"]
        assert revoked_result.status_code == 400


async def test_single_use_invitation_is_hashed_consumed_once_and_audited(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as admin:
        await create_admin_and_login(admin, session_factory)
        invitation = await create_invitation(admin)
        code = invitation["invitation_code"]
        assert code.startswith("GL-")
        assert len(code) >= 24

        listing = await admin.get("/api/v1/admin/invitations")
        assert listing.status_code == 200
        listed = listing.json()["items"][0]
        assert "invitation_code" not in listed
        assert "code_hash" not in listed
        assert listed["code_hint"].endswith("••••")

        test_app.state.settings.registration_mode = "invite_only"
        first = await admin.post(
            "/api/v1/auth/register",
            json=invite_registration_payload(code, "invited@example.com"),
        )
        second = await admin.post(
            "/api/v1/auth/register",
            json=invite_registration_payload(code, "second@example.com"),
        )
        assert first.status_code == 201
        assert first.json()["account_status"] == "active"
        assert first.json()["registration_source"] == "platform_invitation"
        assert second.status_code == 400

        async with session_factory() as session:
            stored = await session.get(PlatformInvitation, uuid.UUID(invitation["id"]))
            user = await session.scalar(select(User).where(User.email == "invited@example.com"))
            assert stored is not None and user is not None
            assert stored.used_count == 1
            assert stored.status == "exhausted"
            assert stored.code_hash != code
            assert code not in stored.code_hash
            assert user.registered_via_invitation_id == stored.id
            events = set(await session.scalars(select(PlatformAuditLog.event_type)))
            assert {"admin_created_invitation", "user_registered"} <= events


async def test_email_constraint_and_failed_user_creation_do_not_consume_invitation(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as admin:
        await create_admin_and_login(admin, session_factory)
        constrained = await create_invitation(admin, email="bound@example.com")
        duplicate = await create_invitation(admin)
        test_app.state.settings.registration_mode = "invite_only"

        wrong = await admin.post(
            "/api/v1/auth/register",
            json=invite_registration_payload(constrained["invitation_code"], "wrong@example.com"),
        )
        duplicate_user = await admin.post(
            "/api/v1/auth/register",
            json=invite_registration_payload(
                duplicate["invitation_code"], "platform-admin@example.com"
            ),
        )
        correct = await admin.post(
            "/api/v1/auth/register",
            json=invite_registration_payload(constrained["invitation_code"], "BOUND@example.com"),
        )
        assert wrong.status_code == 400
        assert duplicate_user.status_code == 409
        assert correct.status_code == 201

        async with session_factory() as session:
            failed_invitation = await session.get(PlatformInvitation, uuid.UUID(duplicate["id"]))
            assert failed_invitation is not None
            assert failed_invitation.used_count == 0
            assert failed_invitation.status == "active"


async def test_admin_user_search_status_and_existing_session_invalidation(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
        httpx.AsyncClient(transport=transport, base_url="http://test") as member,
    ):
        await create_admin_and_login(admin, session_factory)
        member_user = await register_open(member, "status-member@example.com", "状态测试")
        await login(member, "status-member@example.com")

        search = await admin.get("/api/v1/admin/users?search=状态&page_size=1")
        assert search.status_code == 200
        assert search.json()["total"] == 1
        assert search.json()["items"][0]["family_count"] == 0

        suspended = await admin.patch(
            f"/api/v1/admin/users/{member_user['id']}/status",
            json={"account_status": "suspended"},
        )
        assert suspended.status_code == 200
        assert suspended.json()["account_status"] == "suspended"
        assert (await member.get("/api/v1/auth/me")).status_code == 401
        assert (
            await member.post(
                "/api/v1/auth/login",
                json={"email": "status-member@example.com", "password": PASSWORD},
            )
        ).status_code == 401

        filtered = await admin.get("/api/v1/admin/users?account_status=suspended")
        assert filtered.status_code == 200
        assert filtered.json()["total"] == 1
        reactivated = await admin.patch(
            f"/api/v1/admin/users/{member_user['id']}/status",
            json={"account_status": "active"},
        )
        assert reactivated.status_code == 200
        assert (await login(member, "status-member@example.com"))["account_status"] == "active"


async def test_normal_user_cannot_manage_platform_and_admin_has_no_family_access(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as owner,
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
    ):
        await register_open(owner, "private-owner-phase14@example.com")
        await login(owner, "private-owner-phase14@example.com")
        family = await owner.post("/api/v1/families", json={"name": "Phase 14 Private"})
        child = await owner.post(
            f"/api/v1/families/{family.json()['id']}/children",
            json={"display_name": "Private Child", "birth_date": "2020-01-01"},
        )
        assert (await owner.get("/api/v1/admin/users")).status_code == 403
        assert (await owner.get("/api/v1/admin/invitations")).status_code == 403

        await create_admin_and_login(admin, session_factory, "privacy-admin@example.com")
        assert (await admin.get("/api/v1/admin/users")).status_code == 200
        assert (await admin.get(f"/api/v1/families/{family.json()['id']}")).status_code == 404
        assert (await admin.get(f"/api/v1/children/{child.json()['id']}")).status_code == 404


async def test_password_change_revokes_other_sessions_and_logout_all_revokes_current(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as current,
        httpx.AsyncClient(transport=transport, base_url="http://test") as other,
    ):
        user = await register_open(current, "password-phase14@example.com")
        await login(current, "password-phase14@example.com")
        await login(other, "password-phase14@example.com")
        changed = await current.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": PASSWORD,
                "new_password": NEW_PASSWORD,
                "confirm_password": NEW_PASSWORD,
            },
        )
        assert changed.status_code == 200
        assert (await current.get("/api/v1/auth/me")).status_code == 200
        assert (await other.get("/api/v1/auth/me")).status_code == 401
        assert (
            await other.post(
                "/api/v1/auth/login",
                json={"email": "password-phase14@example.com", "password": PASSWORD},
            )
        ).status_code == 401
        await login(other, "password-phase14@example.com", NEW_PASSWORD)

        async with session_factory() as session:
            stored = await session.get(User, uuid.UUID(user["id"]))
            assert stored is not None
            assert stored.password_hash not in {PASSWORD, NEW_PASSWORD}
            assert verify_password(NEW_PASSWORD, stored.password_hash)

        logout_all = await current.post("/api/v1/auth/logout-all")
        assert logout_all.status_code == 204
        assert (await current.get("/api/v1/auth/me")).status_code == 401
        assert (await other.get("/api/v1/auth/me")).status_code == 401


async def test_login_rate_limit_is_enforced(client: httpx.AsyncClient, test_app: FastAPI) -> None:
    await register_open(client, "rate-limit@example.com")
    test_app.state.settings.auth_login_rate_limit = 2
    for _ in range(2):
        failure = await client.post(
            "/api/v1/auth/login",
            json={"email": "rate-limit@example.com", "password": "wrong"},
        )
        assert failure.status_code == 401
    limited = await client.post(
        "/api/v1/auth/login",
        json={"email": "rate-limit@example.com", "password": "wrong"},
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"]


async def test_open_mode_marks_compatibility_accounts_legacy(
    client: httpx.AsyncClient,
) -> None:
    user = await register_open(client, "legacy-compatible@example.com")
    assert user["account_status"] == AccountStatus.ACTIVE
    assert user["registration_source"] == RegistrationSource.LEGACY
