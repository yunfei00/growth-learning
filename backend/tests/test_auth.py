"""Account registration and browser-session authentication tests."""

import httpx
import pytest

pytestmark = pytest.mark.anyio


async def register(client: httpx.AsyncClient, email: str = "parent@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "家长",
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_registration_normalizes_email_and_never_returns_hash(
    client: httpx.AsyncClient,
) -> None:
    payload = await register(client, "Parent@Example.COM")

    assert payload["email"] == "parent@example.com"
    assert payload["display_name"] == "家长"
    assert payload["system_role"] == "user"
    assert "password" not in payload
    assert "password_hash" not in payload


async def test_duplicate_email_is_rejected_case_insensitively(client: httpx.AsyncClient) -> None:
    await register(client)

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "PARENT@example.com",
            "display_name": "另一位家长",
            "password": "another-secure-password",
        },
    )

    assert response.status_code == 409


async def test_login_failure_uses_generic_error(client: httpx.AsyncClient) -> None:
    await register(client)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "parent@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


async def test_login_me_logout_browser_session(client: httpx.AsyncClient) -> None:
    user = await register(client)
    assert (await client.get("/api/v1/auth/me")).status_code == 401

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "parent@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert login.status_code == 200
    assert login.json()["id"] == user["id"]
    cookie = login.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "parent@example.com"

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_login_cookie_uses_configured_proxy_path(client: httpx.AsyncClient, test_app) -> None:
    await register(client, "proxy@example.com")
    test_app.state.settings.auth_cookie_path = "/growth/api"

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "proxy@example.com",
            "password": "correct-horse-battery-staple",
        },
    )

    assert response.status_code == 200
    assert "Path=/growth/api" in response.headers["set-cookie"]
