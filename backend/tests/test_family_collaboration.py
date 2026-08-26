"""Family collaboration keeps identity, permissions, and child evidence separate."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ChildKnowledgeState, ChineseCharacter, KnowledgePoint, LearningRecord


async def register_and_login(
    client: httpx.AsyncClient, email: str, display_name: str
) -> dict[str, object]:
    password = "correct-horse-battery"
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": display_name, "password": password},
    )
    assert registered.status_code == 201
    logged_in = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert logged_in.status_code == 200
    return registered.json()


async def create_family_and_child(client: httpx.AsyncClient) -> tuple[dict, dict]:
    family_response = await client.post("/api/v1/families", json={"name": "协作家庭"})
    assert family_response.status_code == 201
    family = family_response.json()
    child_response = await client.post(
        f"/api/v1/families/{family['id']}/children",
        json={
            "display_name": "小树",
            "nickname": "树树",
            "birth_date": "2021-03-15",
            "gender": "female",
        },
    )
    assert child_response.status_code == 201
    return family, child_response.json()


async def create_invitation(
    client: httpx.AsyncClient,
    family_id: str,
    *,
    email: str,
    role: str = "companion",
) -> dict:
    response = await client.post(
        f"/api/v1/families/{family_id}/invitations",
        json={
            "email_constraint": email,
            "role_to_grant": role,
            "expires_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def seed_character(
    session_factory: async_sessionmaker[AsyncSession], character: str
) -> uuid.UUID:
    async with session_factory() as session:
        point = KnowledgePoint(
            type="chinese_character",
            status="active",
            title=character,
            canonical_key=f"collaboration-{character}-{uuid.uuid4()}",
            source_type="test",
        )
        session.add(point)
        await session.flush()
        session.add(
            ChineseCharacter(
                knowledge_point_id=point.id,
                character=character,
                pinyin="shù",
                common_words=[],
                tags=[],
                is_enabled=True,
            )
        )
        await session.commit()
        return point.id


@pytest.mark.anyio
async def test_existing_user_accepts_email_bound_invitation_idempotently(
    test_app: FastAPI,
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
        httpx.AsyncClient(transport=transport, base_url="http://test") as invited,
        httpx.AsyncClient(transport=transport, base_url="http://test") as stranger,
    ):
        await register_and_login(admin, "owner@example.com", "爸爸")
        invited_user = await register_and_login(invited, "member@example.com", "妈妈")
        await register_and_login(stranger, "stranger@example.com", "陌生人")
        family, child = await create_family_and_child(admin)
        invitation = await create_invitation(
            admin, family["id"], email="member@example.com", role="admin"
        )

        pending = await invited.get("/api/v1/family-invitations/pending")
        assert pending.status_code == 200
        assert [item["id"] for item in pending.json()] == [invitation["id"]]

        wrong_email = await stranger.post(
            "/api/v1/family-invitations/accept",
            json={"invitation_code": invitation["invitation_code"]},
        )
        assert wrong_email.status_code == 403

        accepted = await invited.post(
            "/api/v1/family-invitations/accept",
            json={"invitation_code": invitation["invitation_code"]},
        )
        assert accepted.status_code == 200
        assert accepted.json()["family_id"] == family["id"]
        assert accepted.json()["role"] == "admin"
        assert accepted.json()["already_member"] is False

        accepted_again = await invited.post(
            "/api/v1/family-invitations/accept",
            json={"invitation_code": invitation["invitation_code"]},
        )
        assert accepted_again.status_code == 200
        assert accepted_again.json()["already_member"] is True

        families = await invited.get("/api/v1/families")
        assert families.status_code == 200
        assert [item["id"] for item in families.json()] == [family["id"]]
        assert (await invited.get(f"/api/v1/children/{child['id']}")).status_code == 200

        members = await admin.get(f"/api/v1/families/{family['id']}/members")
        invited_member = next(
            item for item in members.json() if item["user"]["id"] == invited_user["id"]
        )
        assert invited_member["role"] == "admin"

        invalid = await stranger.post(
            "/api/v1/family-invitations/accept",
            json={"invitation_code": "GLF-NOT-A-REAL-CODE"},
        )
        assert invalid.status_code == 404


@pytest.mark.anyio
async def test_expired_revoked_and_companion_invitation_attempts_are_denied(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
        httpx.AsyncClient(transport=transport, base_url="http://test") as member,
    ):
        await register_and_login(admin, "admin@example.com", "管理员")
        await register_and_login(member, "companion@example.com", "陪伴者")
        family, _ = await create_family_and_child(admin)

        expired = await create_invitation(admin, family["id"], email="companion@example.com")
        async with session_factory() as session:
            from app.models import FamilyInvitation

            row = await session.get(FamilyInvitation, uuid.UUID(expired["id"]))
            assert row is not None
            row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
            await session.commit()
        expired_accept = await member.post(
            "/api/v1/family-invitations/accept",
            json={"invitation_code": expired["invitation_code"]},
        )
        assert expired_accept.status_code == 410

        revoked = await create_invitation(admin, family["id"], email="companion@example.com")
        revoked_response = await admin.post(
            f"/api/v1/families/{family['id']}/invitations/{revoked['id']}/revoke"
        )
        assert revoked_response.status_code == 200
        revoked_accept = await member.post(
            "/api/v1/family-invitations/accept",
            json={"invitation_code": revoked["invitation_code"]},
        )
        assert revoked_accept.status_code == 409

        active = await create_invitation(admin, family["id"], email="companion@example.com")
        assert (
            await member.post(
                f"/api/v1/family-invitations/{active['id']}/accept"
            )
        ).status_code == 200
        denied = await member.post(
            f"/api/v1/families/{family['id']}/invitations",
            json={
                "email_constraint": "another@example.com",
                "role_to_grant": "companion",
                "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
        )
        assert denied.status_code == 403


@pytest.mark.anyio
async def test_member_removal_preserves_actor_and_revokes_next_request(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
        httpx.AsyncClient(transport=transport, base_url="http://test") as companion,
    ):
        admin_user = await register_and_login(admin, "parent-a@example.com", "爸爸")
        companion_user = await register_and_login(companion, "parent-b@example.com", "妈妈")
        family, child = await create_family_and_child(admin)
        invitation = await create_invitation(
            admin, family["id"], email="parent-b@example.com", role="companion"
        )
        assert (
            await companion.post(
                "/api/v1/family-invitations/accept",
                json={"invitation_code": invitation["invitation_code"]},
            )
        ).status_code == 200

        members = (await admin.get(f"/api/v1/families/{family['id']}/members")).json()
        owner_member = next(item for item in members if item["user"]["id"] == admin_user["id"])
        companion_member = next(
            item for item in members if item["user"]["id"] == companion_user["id"]
        )
        last_admin = await admin.patch(
            f"/api/v1/families/{family['id']}/members/{owner_member['id']}",
            json={"role": "companion"},
        )
        assert last_admin.status_code == 409

        relation = await admin.put(
            f"/api/v1/families/{family['id']}/members/{owner_member['id']}"
            f"/relations/{child['id']}",
            json={"relation": "father"},
        )
        assert relation.status_code == 200
        relation = await admin.put(
            f"/api/v1/families/{family['id']}/members/{companion_member['id']}"
            f"/relations/{child['id']}",
            json={"relation": "mother"},
        )
        assert relation.status_code == 200

        point_id = await seed_character(session_factory, "树")
        learned = await companion.post(
            f"/api/v1/children/{child['id']}/learning-sessions",
            json={
                "source": "parent_assisted",
                "items": [
                    {
                        "knowledge_point_id": str(point_id),
                        "activity_type": "introduced",
                    }
                ],
            },
        )
        assert learned.status_code == 201

        history = await admin.get(
            f"/api/v1/children/{child['id']}/character-learning-history"
        )
        assert history.status_code == 200
        assert history.json()["total_records"] == 1
        learned_by_admin = await admin.post(
            f"/api/v1/children/{child['id']}/learning-sessions",
            json={
                "source": "parent_assisted",
                "items": [
                    {
                        "knowledge_point_id": str(point_id),
                        "activity_type": "relearned",
                    }
                ],
            },
        )
        assert learned_by_admin.status_code == 201
        shared_history = await companion.get(
            f"/api/v1/children/{child['id']}/character-learning-history"
        )
        assert shared_history.status_code == 200
        assert shared_history.json()["total_records"] == 2
        activity = await admin.get(f"/api/v1/families/{family['id']}/activity")
        assert activity.status_code == 200
        assert {item["actor_display_name"] for item in activity.json()} >= {"爸爸", "妈妈"}

        removed = await admin.delete(
            f"/api/v1/families/{family['id']}/members/{companion_member['id']}"
        )
        assert removed.status_code == 204
        assert (await companion.get(f"/api/v1/children/{child['id']}")).status_code == 404

        async with session_factory() as session:
            actor_ids = set(
                (
                    await session.scalars(
                        select(LearningRecord.actor_user_id).where(
                            LearningRecord.child_id == uuid.UUID(child["id"])
                        )
                    )
                ).all()
            )
            state_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(ChildKnowledgeState)
                    .where(ChildKnowledgeState.child_id == uuid.UUID(child["id"]))
                )
                or 0
            )
        assert actor_ids == {
            uuid.UUID(admin_user["id"]),
            uuid.UUID(companion_user["id"]),
        }
        assert state_count == 1


@pytest.mark.anyio
async def test_multiple_children_edit_archive_and_restore(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_and_login(client, "multi-child@example.com", "家长")
    family, first = await create_family_and_child(client)
    second_response = await client.post(
        f"/api/v1/families/{family['id']}/children",
        json={"display_name": "小花", "birth_date": "2023-05-01", "gender": None},
    )
    assert second_response.status_code == 201
    second = second_response.json()

    listed = await client.get(f"/api/v1/families/{family['id']}/children")
    assert {item["id"] for item in listed.json()} == {first["id"], second["id"]}

    edited = await client.patch(
        f"/api/v1/children/{second['id']}",
        json={"display_name": "小花朵", "nickname": "花花"},
    )
    assert edited.status_code == 200
    assert edited.json()["nickname"] == "花花"

    archived = await client.post(f"/api/v1/children/{second['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["is_archived"] is True
    active = await client.get(f"/api/v1/families/{family['id']}/children")
    assert [item["id"] for item in active.json()] == [first["id"]]
    all_children = await client.get(
        f"/api/v1/families/{family['id']}/children?include_archived=true"
    )
    assert len(all_children.json()) == 2

    restored = await client.post(f"/api/v1/children/{second['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["is_archived"] is False

    point_id = await seed_character(session_factory, "花")
    learned = await client.post(
        f"/api/v1/children/{first['id']}/learning-sessions",
        json={
            "source": "parent_assisted",
            "items": [
                {"knowledge_point_id": str(point_id), "activity_type": "introduced"}
            ],
        },
    )
    assert learned.status_code == 201
    async with session_factory() as session:
        sibling_state_counts = {
            child_id: int(
                await session.scalar(
                    select(func.count())
                    .select_from(ChildKnowledgeState)
                    .where(ChildKnowledgeState.child_id == uuid.UUID(child_id))
                )
                or 0
            )
            for child_id in (first["id"], second["id"])
        }
    assert sibling_state_counts == {first["id"]: 1, second["id"]: 0}
