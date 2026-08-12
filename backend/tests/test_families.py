"""Family and child APIs enforce the household authorization boundary."""

import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import FamilyMember, FamilyRole


async def create_account(
    client: httpx.AsyncClient, *, email: str, name: str = "Adult"
) -> dict[str, object]:
    password = "correct-horse-battery"
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": name, "password": password},
    )
    assert registered.status_code == 201
    logged_in = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert logged_in.status_code == 200
    return registered.json()


async def create_family(client: httpx.AsyncClient, name: str = "贾家") -> dict[str, object]:
    response = await client.post("/api/v1/families", json={"name": name})
    assert response.status_code == 201
    return response.json()


async def create_child(
    client: httpx.AsyncClient, family_id: str, name: str = "小树"
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/families/{family_id}/children",
        json={
            "display_name": name,
            "nickname": "树树",
            "birth_date": "2021-03-15",
            "gender": "female",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.anyio
async def test_family_routes_require_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/families")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_admin_can_create_read_update_family_and_list_members(
    client: httpx.AsyncClient,
) -> None:
    user = await create_account(client, email="admin@example.com", name="家长")
    family = await create_family(client)

    assert family["name"] == "贾家"
    assert family["current_role"] == "admin"

    listed = await client.get("/api/v1/families")
    assert listed.status_code == 200
    assert listed.json() == [family]

    fetched = await client.get(f"/api/v1/families/{family['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == family

    updated = await client.patch(f"/api/v1/families/{family['id']}", json={"name": "我们的家"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "我们的家"

    members = await client.get(f"/api/v1/families/{family['id']}/members")
    assert members.status_code == 200
    assert members.json()[0]["role"] == "admin"
    assert members.json()[0]["user"] == {
        "id": user["id"],
        "email": "admin@example.com",
        "display_name": "家长",
    }


@pytest.mark.anyio
async def test_admin_can_create_list_read_and_update_child(client: httpx.AsyncClient) -> None:
    await create_account(client, email="parent@example.com")
    family = await create_family(client)
    child = await create_child(client, str(family["id"]))

    assert child["family_id"] == family["id"]
    assert child["display_name"] == "小树"
    assert "age" not in child

    listed = await client.get(f"/api/v1/families/{family['id']}/children")
    assert listed.status_code == 200
    assert listed.json() == [child]

    fetched = await client.get(f"/api/v1/children/{child['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == child

    updated = await client.patch(
        f"/api/v1/children/{child['id']}",
        json={"display_name": "大树", "nickname": None, "gender": None},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "大树"
    assert updated.json()["nickname"] is None
    assert updated.json()["gender"] is None


@pytest.mark.anyio
async def test_cross_family_child_access_is_hidden(
    test_app: FastAPI,
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent_a,
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent_b,
    ):
        await create_account(parent_a, email="parent-a@example.com")
        family_a = await create_family(parent_a, "家庭 A")
        child_a = await create_child(parent_a, str(family_a["id"]), "孩子 A")

        await create_account(parent_b, email="parent-b@example.com")
        family_b = await create_family(parent_b, "家庭 B")
        child_b = await create_child(parent_b, str(family_b["id"]), "孩子 B")

        assert (await parent_a.get(f"/api/v1/children/{child_b['id']}")).status_code == 404
        assert (
            await parent_a.patch(
                f"/api/v1/children/{child_b['id']}", json={"display_name": "越权修改"}
            )
        ).status_code == 404
        assert (
            await parent_a.get(f"/api/v1/families/{family_b['id']}/children")
        ).status_code == 404

        unchanged = await parent_b.get(f"/api/v1/children/{child_b['id']}")
        assert unchanged.status_code == 200
        assert unchanged.json()["display_name"] == "孩子 B"
        assert (await parent_b.get(f"/api/v1/children/{child_a['id']}")).status_code == 404


@pytest.mark.anyio
async def test_companion_has_read_only_family_and_child_access(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
        httpx.AsyncClient(transport=transport, base_url="http://test") as companion,
    ):
        await create_account(admin, email="owner@example.com")
        family = await create_family(admin)
        child = await create_child(admin, str(family["id"]))
        companion_user = await create_account(companion, email="grandma@example.com", name="奶奶")

        async with session_factory() as session:
            session.add(
                FamilyMember(
                    family_id=uuid.UUID(str(family["id"])),
                    user_id=uuid.UUID(str(companion_user["id"])),
                    role=FamilyRole.COMPANION,
                )
            )
            await session.commit()

        visible_family = await companion.get(f"/api/v1/families/{family['id']}")
        assert visible_family.status_code == 200
        assert visible_family.json()["current_role"] == "companion"
        assert (await companion.get(f"/api/v1/children/{child['id']}")).status_code == 200
        assert (await companion.get(f"/api/v1/families/{family['id']}/members")).status_code == 200

        assert (
            await companion.patch(f"/api/v1/families/{family['id']}", json={"name": "不能修改"})
        ).status_code == 403
        assert (
            await companion.post(
                f"/api/v1/families/{family['id']}/children",
                json={"display_name": "不能创建", "birth_date": "2020-01-01"},
            )
        ).status_code == 403
        assert (
            await companion.patch(
                f"/api/v1/children/{child['id']}", json={"display_name": "不能修改"}
            )
        ).status_code == 403
