"""System administration and canonical character catalog security tests."""

import io
import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli.admin import read_password
from app.core.security import verify_password
from app.models import KnowledgeRelation, SystemRole, User
from app.services.admin_provisioning import create_admin, promote_admin, set_admin_password

pytestmark = pytest.mark.anyio

PASSWORD = "local-test-password-only"


async def test_admin_cli_strips_windows_stdin_line_ending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{PASSWORD}\r\n"))
    assert read_password() == PASSWORD


async def register_and_login(
    client: httpx.AsyncClient, email: str, *, name: str = "Test Adult"
) -> dict:
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": name, "password": PASSWORD},
    )
    assert registered.status_code == 201
    logged_in = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert logged_in.status_code == 200
    return registered.json()


async def make_system_admin(
    session_factory: async_sessionmaker[AsyncSession], user_id: str
) -> None:
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(user_id))
        assert user is not None
        user.system_role = SystemRole.ADMIN
        await session.commit()


def character_payload(character: str = "人", pinyin: str = "rén") -> dict:
    return {
        "character": character,
        "pinyin": pinyin,
        "common_words": [f"{character}们", "大人"],
        "simple_meaning": "用于测试的基础释义。",
        "tags": ["starter"],
    }


async def test_admin_provisioning_is_explicit_and_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        created = await create_admin(
            session,
            email="Admin@Example.com",
            display_name="System Admin",
            password=PASSWORD,
        )
        repeated = await create_admin(
            session,
            email="admin@example.com",
            display_name="Ignored",
            password="different-test-password",
        )
        assert created.action == "created"
        assert repeated.action == "already_admin"
        assert repeated.user.id == created.user.id

        updated = await set_admin_password(
            session, email="admin@example.com", password="updated-test-password"
        )
        assert updated.action == "password_updated"
        assert verify_password("updated-test-password", updated.user.password_hash)


async def test_existing_user_requires_explicit_promotion(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await register_and_login(client, "member@example.com")
    async with session_factory() as session:
        result = await create_admin(
            session,
            email="member@example.com",
            display_name="Ignored",
            password="different-test-password",
        )
        assert result.action == "existing_user"
        assert result.user.system_role == SystemRole.USER
        promoted = await promote_admin(session, email="member@example.com")
        assert promoted.action == "promoted"
        assert promoted.user.id == uuid.UUID(user["id"])


async def test_admin_guard_denies_unauthenticated_normal_and_family_admin(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.get("/api/v1/admin/overview")).status_code == 401

    await register_and_login(client, "family-admin@example.com")
    family = await client.post("/api/v1/families", json={"name": "Test Family"})
    assert family.status_code == 201
    denied = await client.get("/api/v1/admin/overview")
    assert denied.status_code == 403
    assert denied.json()["detail"] == "System administrator permission required"
    assert (
        await client.post("/api/v1/admin/characters", json=character_payload())
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/admin/characters/import",
            json={"version": "1.0", "items": [character_payload()]},
        )
    ).status_code == 403


async def test_system_admin_allowed_but_has_no_implicit_family_access(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent,
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
    ):
        await register_and_login(parent, "parent-private@example.com")
        family = await parent.post("/api/v1/families", json={"name": "Private Family"})
        child = await parent.post(
            f"/api/v1/families/{family.json()['id']}/children",
            json={"display_name": "Private Child", "birth_date": "2020-01-01"},
        )
        assert child.status_code == 201

        admin_user = await register_and_login(admin, "system@example.com")
        await make_system_admin(session_factory, admin_user["id"])
        overview = await admin.get("/api/v1/admin/overview")
        assert overview.status_code == 200
        assert overview.json() == {
            "users": 2,
            "families": 1,
            "children": 1,
            "characters": 0,
        }
        assert (await admin.get(f"/api/v1/children/{child.json()['id']}")).status_code == 404
        assert (await admin.get(f"/api/v1/families/{family.json()['id']}")).status_code == 404


async def test_character_crud_search_archive_and_public_read_boundary(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = await register_and_login(client, "catalog-admin@example.com")
    await make_system_admin(session_factory, admin["id"])

    created = await client.post("/api/v1/admin/characters", json=character_payload())
    assert created.status_code == 201
    character_id = created.json()["id"]
    assert created.json()["status"] == "active"
    assert (
        await client.post("/api/v1/admin/characters", json=character_payload())
    ).status_code == 409

    by_character = await client.get("/api/v1/admin/characters?search=人")
    assert by_character.status_code == 200
    assert by_character.json()["total"] == 1
    by_pinyin = await client.get("/api/v1/admin/characters?search=rén")
    assert by_pinyin.json()["items"][0]["character"] == "人"

    updated = await client.patch(
        f"/api/v1/admin/characters/{character_id}",
        json={
            "pinyin": "rén",
            "common_words": ["人们", "人民"],
            "simple_meaning": "指人类个体。",
            "example_sentence": "人们一起学习。",
            "radical": "人",
            "stroke_count": 2,
            "tags": ["启蒙"],
            "is_enabled": False,
            "status": "archived",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["common_words"] == ["人们", "人民"]
    assert updated.json()["is_enabled"] is False
    assert updated.json()["status"] == "archived"

    assert (await client.get(f"/api/v1/characters/{character_id}")).status_code == 404
    assert (await client.get("/api/v1/characters")).json()["total"] == 0
    assert (
        await client.post("/api/v1/characters", json=character_payload("山", "shān"))
    ).status_code == 405

    enabled = await client.patch(
        f"/api/v1/admin/characters/{character_id}",
        json={"is_enabled": True, "status": "active"},
    )
    assert enabled.status_code == 200
    assert (await client.get(f"/api/v1/characters/{character_id}")).status_code == 200


async def test_bulk_import_is_idempotent_and_reports_changes(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = await register_and_login(client, "import-admin@example.com")
    await make_system_admin(session_factory, admin["id"])
    payload = {
        "version": "1.0",
        "items": [character_payload("山", "shān"), character_payload("水", "shuǐ")],
    }
    first = await client.post("/api/v1/admin/characters/import", json=payload)
    assert first.status_code == 200
    assert first.json() == {"created": 2, "updated": 0, "skipped": 0, "errors": []}

    second = await client.post("/api/v1/admin/characters/import", json=payload)
    assert second.status_code == 200
    assert second.json() == {"created": 0, "updated": 0, "skipped": 2, "errors": []}


async def test_starter_import_and_knowledge_relations_are_idempotent(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = await register_and_login(client, "starter-admin@example.com")
    await make_system_admin(session_factory, admin["id"])
    first = await client.post("/api/v1/admin/characters/import-starter")
    assert first.status_code == 200
    assert first.json()["created"] == 200
    second = await client.post("/api/v1/admin/characters/import-starter")
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["skipped"] == 200

    async with session_factory() as session:
        relations = list(await session.scalars(select(KnowledgeRelation)))
        assert len(relations) == 7

    page = await client.get("/api/v1/admin/characters?page=1&page_size=50")
    assert page.status_code == 200
    assert page.json()["total"] == 200
    assert page.json()["pages"] == 4


async def test_relation_endpoint_rejects_duplicates_and_self_relations(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = await register_and_login(client, "relation-admin@example.com")
    await make_system_admin(session_factory, admin["id"])
    for payload in (character_payload("木", "mù"), character_payload("林", "lín")):
        assert (await client.post("/api/v1/admin/characters", json=payload)).status_code == 201
    listing = (await client.get("/api/v1/admin/characters?page_size=10")).json()["items"]
    ids = {item["character"]: item["id"] for item in listing}
    relation = {
        "source_id": ids["木"],
        "target_id": ids["林"],
        "relation_type": "derived",
    }
    assert (
        await client.post("/api/v1/admin/knowledge-relations", json=relation)
    ).status_code == 201
    assert (
        await client.post("/api/v1/admin/knowledge-relations", json=relation)
    ).status_code == 409
    relation["target_id"] = relation["source_id"]
    assert (
        await client.post("/api/v1/admin/knowledge-relations", json=relation)
    ).status_code == 422
