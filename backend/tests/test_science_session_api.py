"""Focused contract tests for starting, resuming, and completing science sessions."""

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ExperimentEvidence, ExperimentSession, ScienceExperiment
from app.services.science_catalog import import_starter_science_experiments

pytestmark = pytest.mark.anyio

PASSWORD = "science-session-api-tests-only"


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
