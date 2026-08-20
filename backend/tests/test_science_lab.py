"""Weekend Science Lab catalog, evidence integrity, media, and privacy tests."""

import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.science import get_science_storage
from app.integrations.object_storage import PrivateObjectStorage
from app.models import (
    AssessmentItem,
    ExperimentEvidence,
    ExperimentSession,
    FamilyMember,
    FamilyRole,
    LearningActivityType,
    LearningRecord,
    ScienceExperimentVersion,
    SystemRole,
    User,
)
from app.schemas.knowledge import CharacterCreate
from app.services.character_catalog import create_character
from app.services.science_media import validate_media

pytestmark = pytest.mark.anyio
PASSWORD = "science-tests-only-password"


async def test_media_validation_accepts_supported_kinds_and_rejects_unsafe(
    test_app: FastAPI,
) -> None:
    settings = test_app.state.settings
    assert (
        validate_media(
            settings=settings,
            filename="a.jpg",
            mime_type="image/jpeg",
            content=b"\xff\xd8\xffimage",
        )[0]
        == "image"
    )
    assert (
        validate_media(
            settings=settings,
            filename="a.mp4",
            mime_type="video/mp4",
            content=b"\x00\x00\x00\x18ftypmp42",
        )[0]
        == "video"
    )
    assert (
        validate_media(
            settings=settings,
            filename="a.ogg",
            mime_type="audio/ogg",
            content=b"OggSaudio",
        )[0]
        == "audio"
    )
    with pytest.raises(ValueError, match="仅支持"):
        validate_media(settings=settings, filename="a.svg", mime_type="image/svg+xml", content=b"a")
    with pytest.raises(ValueError, match="内容"):
        validate_media(
            settings=settings,
            filename="spoofed.jpg",
            mime_type="image/jpeg",
            content=b"not-a-jpeg",
        )
    assert (
        validate_media(
            settings=settings,
            filename="..\\..\\private.jpg",
            mime_type="image/jpeg",
            content=b"\xff\xd8\xffimage",
        )[2]
        == "private.jpg"
    )


class FakePrivateStorage(PrivateObjectStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, object_key: str, content: bytes, mime_type: str) -> None:
        del mime_type
        self.objects[object_key] = content

    async def read(self, object_key: str) -> bytes:
        return self.objects[object_key]

    async def remove(self, object_key: str) -> None:
        self.objects.pop(object_key, None)


async def register_and_login(client: httpx.AsyncClient, email: str) -> dict:
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "科学陪伴者", "password": PASSWORD},
    )
    assert registered.status_code == 201
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    return registered.json()


async def make_system_admin(
    session_factory: async_sessionmaker[AsyncSession], user_id: str
) -> None:
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(user_id))
        assert user is not None
        user.system_role = SystemRole.ADMIN
        await session.commit()


async def add_companion(
    session_factory: async_sessionmaker[AsyncSession], family_id: str, user_id: str
) -> None:
    async with session_factory() as session:
        session.add(
            FamilyMember(
                family_id=uuid.UUID(family_id),
                user_id=uuid.UUID(user_id),
                role=FamilyRole.COMPANION,
            )
        )
        await session.commit()


def experiment_payload(point_id: str) -> dict:
    return {
        "canonical_key": "test_paper_bridge",
        "title": "纸桥承重",
        "description": "用纸和积木搭一座桥，观察不同折法的承重变化。",
        "age_min": 4,
        "age_max": 9,
        "difficulty": "intro",
        "estimated_duration_minutes": 20,
        "guiding_question": "一张纸怎样才能托起更多积木？",
        "expected_phenomenon": "折出波纹后，纸桥可以托起更多积木。",
        "child_friendly_explanation": "折痕让纸在不同方向互相支撑。",
        "parent_scientific_explanation": "折叠改变截面形状并提高抗弯刚度。",
        "safety_notes": ["成人陪伴，避免积木掉落砸脚。"],
        "common_failure_reasons": ["桥墩距离太远。"],
        "follow_up_questions": ["换一种折法会怎样？"],
        "likely_child_questions": ["为什么平纸容易弯？"],
        "steps": ["先提问", "预测", "搭桥", "逐个放积木", "观察并记录"],
        "status": "enabled",
        "source_type": "system",
        "requirements": [
            {
                "material": {
                    "canonical_key": "test_paper",
                    "name": "测试用纸",
                    "aliases": ["纸张"],
                    "category": "纸品",
                    "is_active": True,
                },
                "quantity_text": "2张",
                "is_required": True,
                "substitution_notes": "可使用旧打印纸。",
                "position": 0,
            }
        ],
        "related_knowledge_point_ids": [point_id],
    }


async def test_science_admin_catalog_and_starter_import_are_protected_and_idempotent(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/v1/admin/science/experiments")).status_code == 401
        normal = await register_and_login(client, "science-normal@example.com")
        assert (await client.get("/api/v1/admin/science/experiments")).status_code == 403

        family = await client.post("/api/v1/families", json={"name": "家庭管理员"})
        assert family.status_code == 201
        assert (await client.get("/api/v1/admin/science/experiments")).status_code == 403

        await make_system_admin(session_factory, normal["id"])
        first = await client.post("/api/v1/admin/science/import-starter")
        assert first.status_code == 200
        assert first.json()["created"] >= 10
        assert first.json()["errors"] == []
        second = await client.post("/api/v1/admin/science/import-starter")
        assert second.status_code == 200
        assert second.json()["created"] == 0
        assert second.json()["updated"] == 0
        assert second.json()["skipped"] == first.json()["created"]

        catalog = await client.get("/api/v1/science/experiments?search=纸桥")
        assert catalog.status_code == 200
        assert catalog.json()["total"] >= 1


async def test_resumable_science_evidence_media_completion_and_privacy(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    storage = FakePrivateStorage()
    test_app.dependency_overrides[get_science_storage] = lambda: storage
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent,
        httpx.AsyncClient(transport=transport, base_url="http://test") as companion,
        httpx.AsyncClient(transport=transport, base_url="http://test") as outsider,
        httpx.AsyncClient(transport=transport, base_url="http://test") as system_admin,
    ):
        parent_user = await register_and_login(parent, "science-parent@example.com")
        family_response = await parent.post("/api/v1/families", json={"name": "周末科学家庭"})
        family = family_response.json()
        child_response = await parent.post(
            f"/api/v1/families/{family['id']}/children",
            json={"display_name": "小小实验员", "birth_date": "2020-06-01"},
        )
        child = child_response.json()

        companion_user = await register_and_login(companion, "science-companion@example.com")
        await add_companion(session_factory, family["id"], companion_user["id"])
        await register_and_login(outsider, "science-outsider@example.com")
        admin_user = await register_and_login(system_admin, "science-system@example.com")
        await make_system_admin(session_factory, admin_user["id"])

        async with session_factory() as session:
            point, _ = await create_character(
                session,
                CharacterCreate(
                    character="桥",
                    pinyin="qiáo",
                    common_words=["小桥"],
                    simple_meaning="供人通过的建筑。",
                ),
            )
            point_id = str(point.id)
        await make_system_admin(session_factory, parent_user["id"])
        created = await parent.post(
            "/api/v1/admin/science/experiments", json=experiment_payload(point_id)
        )
        assert created.status_code == 201, created.text
        experiment = created.json()

        recommendations = await companion.get(
            f"/api/v1/children/{child['id']}/science/recommendations"
        )
        assert recommendations.status_code == 200
        assert recommendations.json()[0]["experiment"]["id"] == experiment["id"]
        assert "适合当前年龄段" in recommendations.json()[0]["reasons"]

        inventory = await parent.get(f"/api/v1/families/{family['id']}/science/materials")
        material_id = inventory.json()[0]["material"]["id"]
        assert (
            await companion.put(
                f"/api/v1/families/{family['id']}/science/materials",
                json={"items": [{"material_id": material_id, "is_owned": True}]},
            )
        ).status_code == 403
        owned = await parent.put(
            f"/api/v1/families/{family['id']}/science/materials",
            json={"items": [{"material_id": material_id, "is_owned": True}]},
        )
        assert owned.status_code == 200
        assert owned.json()[0]["is_owned"] is True

        started = await companion.post(
            f"/api/v1/children/{child['id']}/experiment-sessions",
            json={
                "experiment_id": experiment["id"],
                "request_key": "science-resume-key-001",
                "start_immediately": True,
            },
        )
        assert started.status_code == 201, started.text
        experiment_session = started.json()
        resumed = await companion.post(
            f"/api/v1/children/{child['id']}/experiment-sessions",
            json={
                "experiment_id": experiment["id"],
                "request_key": "science-resume-key-001",
                "start_immediately": True,
            },
        )
        assert resumed.json()["id"] == experiment_session["id"]

        evidence = await companion.post(
            f"/api/v1/children/{child['id']}/experiment-sessions/"
            f"{experiment_session['id']}/evidence",
            json={
                "items": [
                    {
                        "evidence_type": "prediction",
                        "original_text": "我猜折起来会更高，也会更结实。",
                        "capability_tags": ["prediction", "causal_reasoning"],
                        "client_key": "science-evidence-0001",
                    },
                    {
                        "evidence_type": "child_original_words",
                        "original_text": "纸像小山一样撑住了积木！",
                        "capability_tags": ["observation", "expression"],
                        "client_key": "science-evidence-0002",
                    },
                ]
            },
        )
        assert evidence.status_code == 200
        assert evidence.json()[1]["original_text"] == "纸像小山一样撑住了积木！"
        assert "score" not in evidence.json()[1]

        uploaded = await companion.post(
            f"/api/v1/children/{child['id']}/experiment-sessions/{experiment_session['id']}/media",
            files={
                "file": (
                    "observation.jpg",
                    b"\xff\xd8\xffprivate-image-bytes",
                    "image/jpeg",
                )
            },
        )
        assert uploaded.status_code == 201, uploaded.text
        media = uploaded.json()["media"][0]
        streamed = await companion.get(media["content_url"])
        assert streamed.status_code == 200
        assert streamed.content == b"\xff\xd8\xffprivate-image-bytes"
        invalid = await companion.post(
            f"/api/v1/children/{child['id']}/experiment-sessions/{experiment_session['id']}/media",
            files={"file": ("unsafe.svg", b"<svg/>", "image/svg+xml")},
        )
        assert invalid.status_code == 422

        assert (
            await outsider.get(
                f"/api/v1/children/{child['id']}/experiment-sessions/{experiment_session['id']}"
            )
        ).status_code == 404
        assert (
            await system_admin.get(
                f"/api/v1/children/{child['id']}/experiment-sessions/{experiment_session['id']}"
            )
        ).status_code == 404

        before_assessments = 0
        async with session_factory() as session:
            before_assessments = int(
                await session.scalar(select(func.count()).select_from(AssessmentItem)) or 0
            )
        completed = await companion.post(
            f"/api/v1/children/{child['id']}/experiment-sessions/"
            f"{experiment_session['id']}/complete",
            json={},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert completed.json()["science_exposure_count"] == 1
        repeat = await companion.post(
            f"/api/v1/children/{child['id']}/experiment-sessions/"
            f"{experiment_session['id']}/complete",
            json={},
        )
        assert repeat.status_code == 200
        assert repeat.json()["science_exposure_count"] == 1
        growth_card = await parent.get(
            f"/api/v1/children/{child['id']}/experiment-sessions/"
            f"{experiment_session['id']}/growth-card"
        )
        assert growth_card.status_code == 200
        assert growth_card.json()["child_original_words"] == ["纸像小山一样撑住了积木！"]
        assert "score" not in growth_card.json()

        async with session_factory() as session:
            exposure = await session.scalar(
                select(LearningRecord).where(
                    LearningRecord.child_id == uuid.UUID(child["id"]),
                    LearningRecord.activity_type
                    == LearningActivityType.SCIENCE_EXPERIMENT_EXPOSURE,
                )
            )
            assert exposure is not None
            assert (
                int(await session.scalar(select(func.count()).select_from(AssessmentItem)) or 0)
                == before_assessments
            )
            stored_evidence = list(
                (
                    await session.scalars(
                        select(ExperimentEvidence).order_by(ExperimentEvidence.captured_at)
                    )
                ).all()
            )
            assert stored_evidence[1].original_text == "纸像小山一样撑住了积木！"
            saved_session = await session.get(
                ExperimentSession, uuid.UUID(experiment_session["id"])
            )
            assert saved_session is not None
            version = await session.get(
                ScienceExperimentVersion, saved_session.experiment_version_id
            )
            assert version is not None
            assert version.version_number == 1
            assert version.snapshot == saved_session.experiment_snapshot

        planned = await companion.post(
            f"/api/v1/children/{child['id']}/experiment-sessions",
            json={
                "experiment_id": experiment["id"],
                "request_key": "science-planned-key-001",
                "start_immediately": False,
            },
        )
        assert planned.status_code == 201
        assert planned.json()["status"] == "planned"
        abandoned = await companion.patch(
            f"/api/v1/children/{child['id']}/experiment-sessions/{planned.json()['id']}",
            json={"action": "abandon"},
        )
        assert abandoned.status_code == 200
        assert abandoned.json()["status"] == "abandoned"

        disabled_story = await parent.post(
            f"/api/v1/children/{child['id']}/experiment-sessions/"
            f"{experiment_session['id']}/generate-story",
            json={"difficulty": "normal"},
        )
        assert disabled_story.status_code == 503
        assert disabled_story.json()["detail"] == "AI 服务尚未配置"

    test_app.dependency_overrides.pop(get_science_storage, None)
