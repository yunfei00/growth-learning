"""Focused contract tests for starting, resuming, and completing science sessions."""

import uuid

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.science import get_science_ai_provider, get_science_storage
from app.integrations.ai.fake import FakeAIProvider
from app.integrations.object_storage import PrivateObjectStorage
from app.models import (
    ExperimentEvidence,
    ExperimentMediaAsset,
    ExperimentSession,
    LearningRecord,
    ScienceExperiment,
)
from app.services.science_catalog import import_starter_science_experiments

pytestmark = pytest.mark.anyio

PASSWORD = "science-session-api-tests-only"


class PersistentFakeStorage(PrivateObjectStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, object_key: str, content: bytes, mime_type: str) -> None:
        del mime_type
        self.objects[object_key] = content

    async def read(self, object_key: str) -> bytes:
        return self.objects[object_key]

    async def remove(self, object_key: str) -> None:
        self.objects.pop(object_key, None)


async def science_context(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[dict, ScienceExperiment]:
    suffix = uuid.uuid4().hex
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"science-session-{suffix}@example.com",
            "display_name": "科学陪伴者",
            "password": PASSWORD,
        },
    )
    assert registered.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": f"science-session-{suffix}@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200
    family = await client.post("/api/v1/families", json={"name": "科学测试家庭"})
    assert family.status_code == 201
    child = await client.post(
        f"/api/v1/families/{family.json()['id']}/children",
        json={"display_name": "小小实验员", "birth_date": "2020-06-01"},
    )
    assert child.status_code == 201

    async with session_factory() as session:
        imported = await import_starter_science_experiments(session)
        assert imported.errors == []
        experiment = await session.scalar(
            select(ScienceExperiment).where(ScienceExperiment.canonical_key == "floating_egg")
        )
        assert experiment is not None
        session.expunge(experiment)
    return child.json(), experiment


def start_payload(experiment_id: uuid.UUID, request_key: str) -> dict:
    return {
        "experiment_id": str(experiment_id),
        "timezone": "Asia/Shanghai",
        "request_key": request_key,
        "start_immediately": True,
    }


async def test_start_science_experiment(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    child, experiment = await science_context(client, session_factory)

    response = await client.post(
        f"/api/v1/children/{child['id']}/experiment-sessions",
        json=start_payload(experiment.id, "start-science-experiment-001"),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["child_id"] == child["id"]
    assert body["experiment_id"] == str(experiment.id)
    assert body["status"] == "in_progress"
    assert body["current_step"] == "question"
    assert body["started_at"] is not None
    assert body["completed_at"] is None


async def test_start_science_experiment_requires_child(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, experiment = await science_context(client, session_factory)

    response = await client.post(
        f"/api/v1/children/{uuid.uuid4()}/experiment-sessions",
        json=start_payload(experiment.id, "requires-authorized-child-001"),
    )

    assert response.status_code == 404


async def test_start_science_experiment_invalid_experiment(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    child, _ = await science_context(client, session_factory)

    response = await client.post(
        f"/api/v1/children/{child['id']}/experiment-sessions",
        json=start_payload(uuid.uuid4(), "invalid-science-experiment-001"),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Science experiment not found"


async def test_resume_existing_science_session(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    child, experiment = await science_context(client, session_factory)
    endpoint = f"/api/v1/children/{child['id']}/experiment-sessions"
    first = await client.post(
        endpoint,
        json=start_payload(experiment.id, "resume-science-session-first"),
    )
    assert first.status_code == 201, first.text

    resumed = await client.post(
        endpoint,
        json=start_payload(experiment.id, "resume-science-session-retry"),
    )

    assert resumed.status_code == 201, resumed.text
    assert resumed.json()["id"] == first.json()["id"]
    async with session_factory() as session:
        sessions = list(
            (
                await session.scalars(
                    select(ExperimentSession).where(
                        ExperimentSession.child_id == uuid.UUID(child["id"]),
                        ExperimentSession.experiment_id == experiment.id,
                    )
                )
            ).all()
        )
    assert len(sessions) == 1


async def test_complete_science_experiment(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    child, experiment = await science_context(client, session_factory)
    started = await client.post(
        f"/api/v1/children/{child['id']}/experiment-sessions",
        json=start_payload(experiment.id, "complete-science-experiment-001"),
    )
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]
    session_endpoint = f"/api/v1/children/{child['id']}/experiment-sessions/{session_id}"

    for step in ("prediction", "experiment", "observation", "summary"):
        advanced = await client.patch(
            session_endpoint,
            json={"action": "advance", "current_step": step},
        )
        assert advanced.status_code == 200, advanced.text
        assert advanced.json()["current_step"] == step

    evidence = await client.post(
        f"{session_endpoint}/evidence",
        json={
            "items": [
                {
                    "evidence_type": "observation",
                    "original_text": "盐越来越多时，鸡蛋慢慢浮起来了。",
                    "capability_tags": ["observation", "hands_on"],
                    "client_key": "complete-observation-001",
                },
                {
                    "evidence_type": "child_summary",
                    "original_text": "盐水更能托住鸡蛋。",
                    "capability_tags": ["causal_reasoning", "expression"],
                    "client_key": "complete-summary-001",
                },
            ]
        },
    )
    assert evidence.status_code == 200, evidence.text

    completed = await client.post(
        f"{session_endpoint}/complete",
        json={"parent_note": "已完成浮力观察。"},
    )

    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["current_step"] == "complete"
    assert completed.json()["started_at"] is not None
    assert completed.json()["completed_at"] is not None
    assert completed.json()["parent_note"] == "已完成浮力观察。"

    async with session_factory() as session:
        stored = await session.get(ExperimentSession, uuid.UUID(session_id))
        assert stored is not None
        assert stored.child_id == uuid.UUID(child["id"])
        assert stored.experiment_id == experiment.id
        assert stored.status == "completed"
        assert stored.started_at is not None
        assert stored.completed_at is not None
        observations = list(
            (
                await session.scalars(
                    select(ExperimentEvidence).where(
                        ExperimentEvidence.experiment_session_id == stored.id
                    )
                )
            ).all()
        )
    assert {item.evidence_type for item in observations} == {"observation", "child_summary"}


async def test_completed_experiment_archive_keeps_and_edits_media_without_reopening_status(
    client: httpx.AsyncClient,
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    storage = PersistentFakeStorage()
    ai_provider = FakeAIProvider(
        ['{"parent_tip":"先请孩子复述看到的变化，再一起比较实验前后的不同。"}']
    )
    test_app.dependency_overrides[get_science_storage] = lambda: storage
    test_app.dependency_overrides[get_science_ai_provider] = lambda: ai_provider
    test_app.state.settings.ai_provider = "openai_compatible"
    test_app.state.settings.ai_api_key = SecretStr("test-ai-key")
    test_app.state.settings.ai_model = "test-model"

    child, experiment = await science_context(client, session_factory)
    started = await client.post(
        f"/api/v1/children/{child['id']}/experiment-sessions",
        json=start_payload(experiment.id, "phase-13-archive-session"),
    )
    assert started.status_code == 201
    session_id = started.json()["id"]
    endpoint = f"/api/v1/children/{child['id']}/experiment-sessions/{session_id}"

    for index in range(3):
        uploaded = await client.post(
            f"{endpoint}/media",
            files={
                "file": (
                    f"photo-{index + 1}.jpg",
                    b"\xff\xd8\xff" + bytes([index + 1]),
                    "image/jpeg",
                )
            },
        )
        assert uploaded.status_code == 201, uploaded.text
    assert len(uploaded.json()["media"]) == 3

    completed = await client.post(f"{endpoint}/complete", json={"parent_note": "第一次备注"})
    assert completed.status_code == 200
    completed_body = completed.json()
    created_at = completed_body["created_at"]
    completed_at = completed_body["completed_at"]
    exposure_count = completed_body["science_exposure_count"]

    reopened = await client.get(endpoint)
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "completed"
    assert len(reopened.json()["media"]) == 3
    for media in reopened.json()["media"]:
        content = await client.get(media["content_url"])
        assert content.status_code == 200
        assert content.content.startswith(b"\xff\xd8\xff")

    fourth = await client.post(
        f"{endpoint}/media",
        files={"file": ("photo-4.jpg", b"\xff\xd8\xff\x04", "image/jpeg")},
    )
    assert fourth.status_code == 201, fourth.text
    assert len(fourth.json()["media"]) == 4
    first_media_id = fourth.json()["media"][0]["id"]
    second_media_id = fourth.json()["media"][1]["id"]

    replaced = await client.put(
        f"{endpoint}/media/{first_media_id}",
        files={"file": ("replacement.jpg", b"\xff\xd8\xffreplacement", "image/jpeg")},
    )
    assert replaced.status_code == 200, replaced.text
    replaced_media = next(item for item in replaced.json()["media"] if item["id"] == first_media_id)
    assert replaced_media["original_filename"] == "replacement.jpg"
    assert (await client.get(replaced_media["content_url"])).content.endswith(b"replacement")

    deleted = await client.delete(f"{endpoint}/media/{second_media_id}")
    assert deleted.status_code == 204

    added_evidence = await client.post(
        f"{endpoint}/evidence",
        json={
            "items": [
                {
                    "evidence_type": "observation",
                    "original_text": "原来的实验现象",
                    "capability_tags": ["observation"],
                    "client_key": "phase-13-completed-evidence",
                }
            ]
        },
    )
    assert added_evidence.status_code == 200
    evidence_id = added_evidence.json()[0]["id"]
    edited_evidence = await client.patch(
        f"{endpoint}/evidence/{evidence_id}",
        json={"original_text": "修改后的实验现象和孩子回答"},
    )
    assert edited_evidence.status_code == 200

    updated_note = await client.patch(endpoint, json={"parent_note": "完成后补充的家长备注"})
    assert updated_note.status_code == 200
    final_body = updated_note.json()
    assert final_body["status"] == "completed"
    assert final_body["current_step"] == "complete"
    assert final_body["created_at"] == created_at
    assert final_body["completed_at"] == completed_at
    assert final_body["updated_at"] >= completed_body["updated_at"]
    assert final_body["parent_note"] == "完成后补充的家长备注"
    assert len(final_body["media"]) == 3
    assert any(
        item["original_text"] == "修改后的实验现象和孩子回答" for item in final_body["evidence"]
    )

    forbidden_transition = await client.patch(
        endpoint,
        json={"action": "advance", "current_step": "observation"},
    )
    assert forbidden_transition.status_code == 409
    assert (await client.get(endpoint)).json()["status"] == "completed"
    assert (await client.post(f"{endpoint}/complete", json={})).json()[
        "science_exposure_count"
    ] == exposure_count

    before_records = 0
    async with session_factory() as session:
        before_records = int(
            await session.scalar(select(func.count()).select_from(LearningRecord)) or 0
        )
        assets = list(
            (
                await session.scalars(
                    select(ExperimentMediaAsset).where(
                        ExperimentMediaAsset.experiment_session_id == uuid.UUID(session_id)
                    )
                )
            ).all()
        )
        assert len(assets) == 3
        assert all(
            asset.object_key.startswith(f"science/{child['family_id']}/{session_id}/")
            for asset in assets
        )

    ai_tip = await client.post(f"{endpoint}/ai-parent-tip")
    assert ai_tip.status_code == 200, ai_tip.text
    assert "复述" in ai_tip.json()["parent_tip"]
    assert ai_tip.json()["learning_records_modified"] is False
    assert ai_provider.requests[-1].max_tokens == 1200
    async with session_factory() as session:
        after_records = int(
            await session.scalar(select(func.count()).select_from(LearningRecord)) or 0
        )
    assert after_records == before_records

    test_app.dependency_overrides.pop(get_science_storage, None)
    test_app.dependency_overrides.pop(get_science_ai_provider, None)
