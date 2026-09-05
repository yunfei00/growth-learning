"""Representative literacy diagnostic sampling, evidence, and privacy tests."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AssessmentItem,
    CatalogRelease,
    CharacterCatalogEntry,
    ChildKnowledgeState,
    ChineseCharacter,
    KnowledgePoint,
    KnowledgeStatus,
    KnowledgeType,
    LearningRecord,
    LiteracyEstimate,
    Subject,
)
from app.services.literacy_diagnostic import (
    LITERACY_DIAGNOSTIC_ESTIMATION_VERSION,
    representative_catalog_positions,
    wilson_literacy_estimate,
)

pytestmark = pytest.mark.anyio
PASSWORD = "local-test-password-only"


async def register_and_login(client: httpx.AsyncClient, email: str) -> dict:
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "识字检测家长", "password": PASSWORD},
    )
    assert registered.status_code == 201
    logged_in = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert logged_in.status_code == 200
    return registered.json()


async def create_family_and_child(client: httpx.AsyncClient, suffix: str = "") -> tuple[dict, dict]:
    family_response = await client.post(
        "/api/v1/families", json={"name": f"识字检测家庭{suffix}"}
    )
    assert family_response.status_code == 201
    family = family_response.json()
    child_response = await client.post(
        f"/api/v1/families/{family['id']}/children",
        json={"display_name": f"小树{suffix}", "birth_date": "2021-03-15"},
    )
    assert child_response.status_code == 201
    return family, child_response.json()


async def seed_catalog(
    session_factory: async_sessionmaker[AsyncSession], count: int = 240
) -> dict[str, int]:
    """Create one current ordered catalog in a single transaction."""

    async with session_factory() as session:
        release = CatalogRelease(
            catalog_version=f"diagnostic-test-{count}",
            source_type="project_curated",
            source_name="Growth Learning Test",
            imported_at=datetime.now(UTC),
            item_count=count,
            is_current=True,
            metadata_json={},
        )
        session.add(release)
        await session.flush()
        id_to_order: dict[str, int] = {}
        for index in range(count):
            point_id = uuid.uuid4()
            glyph = chr(0x4E00 + index)
            session.add(
                KnowledgePoint(
                    id=point_id,
                    subject=Subject.CHINESE,
                    type=KnowledgeType.CHINESE_CHARACTER,
                    status=KnowledgeStatus.ACTIVE,
                    title=glyph,
                    canonical_key=f"zh-char:diagnostic-test:{index}",
                    source_type="project_curated",
                )
            )
            session.add(
                ChineseCharacter(
                    knowledge_point_id=point_id,
                    character=glyph,
                    pinyin="yi1",
                    common_words=[],
                    accepted_readings=[],
                    tags=[],
                    is_enabled=True,
                )
            )
            session.add(
                CharacterCatalogEntry(
                    catalog_release_id=release.id,
                    knowledge_point_id=point_id,
                    order_index=index,
                )
            )
            id_to_order[str(point_id)] = index
        await session.commit()
        return id_to_order


def test_representative_positions_cover_all_120_ten_character_strata() -> None:
    positions = representative_catalog_positions(1200, seed=42, sample_size=120)
    assert len(positions) == 120
    assert len(set(positions)) == 120
    assert all(index * 10 <= position < (index + 1) * 10 for index, position in enumerate(positions))
    assert positions == representative_catalog_positions(1200, seed=42, sample_size=120)
    assert positions != representative_catalog_positions(1200, seed=43, sample_size=120)


def test_wilson_estimate_scales_only_independent_correct_answers() -> None:
    estimate, lower, upper = wilson_literacy_estimate(36, 120, 1200)
    assert estimate == 360
    assert 0 <= lower < estimate < upper <= 1200
    assert wilson_literacy_estimate(0, 120, 1200)[0] == 0
    assert wilson_literacy_estimate(120, 120, 1200)[0] == 1200


async def test_standard_diagnostic_is_resumable_and_only_updates_tested_characters(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_and_login(client, "literacy-owner@example.com")
    _, child = await create_family_and_child(client)
    id_to_order = await seed_catalog(session_factory, 240)

    started = await client.post(f"/api/v1/children/{child['id']}/literacy-diagnostic/start")
    assert started.status_code == 200
    body = started.json()
    assert body["source"] == "literacy_diagnostic"
    assert body["total_items"] == 120
    assert body["segment_size"] == 30
    assert body["total_segments"] == 4
    assert body["completed_items"] == 0
    assert body["result"] is None

    target_ids = [item["knowledge_point_id"] for item in body["targets"]]
    assert len(target_ids) == len(set(target_ids)) == 120
    # A 240-item fixture becomes 120 equal two-character strata.
    for index, target_id in enumerate(target_ids):
        assert index * 2 <= id_to_order[target_id] < (index + 1) * 2

    resumed = await client.post(f"/api/v1/children/{child['id']}/literacy-diagnostic/start")
    assert resumed.status_code == 200
    assert resumed.json()["id"] == body["id"]
    assert [item["knowledge_point_id"] for item in resumed.json()["targets"]] == target_ids

    first = body["targets"][0]
    technical = await client.post(
        f"/api/v1/children/{child['id']}/literacy-diagnostic/sessions/{body['id']}/speech-attempts",
        json={
            "knowledge_point_id": first["knowledge_point_id"],
            "attempt_index": 1,
            "provider": "browser_speech_recognition",
            "decision": "no_speech",
            "provider_metadata": {"error_code": "no_speech"},
        },
    )
    assert technical.status_code == 200
    assert technical.json()["decision"] == "no_speech"

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(AssessmentItem)) == 0
        assert await session.scalar(select(func.count()).select_from(LearningRecord)) == 0
        assert await session.scalar(select(func.count()).select_from(ChildKnowledgeState)) == 0

    first_answer = await client.post(
        f"/api/v1/children/{child['id']}/literacy-diagnostic/sessions/{body['id']}/items",
        json={
            "items": [
                {
                    "knowledge_point_id": first["knowledge_point_id"],
                    "outcome": "correct",
                    "evaluation_method": "parent_manual",
                    "response_time_ms": 900,
                }
            ]
        },
    )
    assert first_answer.status_code == 200
    assert first_answer.json()["completed_items"] == 1
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(LearningRecord)) == 0
        assert await session.scalar(select(func.count()).select_from(ChildKnowledgeState)) == 1

    # Complete the persisted sample in child-sized batches.  Overall mix:
    # 60 independent correct, 30 uncertain, 30 incorrect.
    remaining_payloads: list[dict] = []
    for index, target in enumerate(body["targets"][1:], start=1):
        outcome = "correct" if index < 60 else "uncertain" if index < 90 else "incorrect"
        remaining_payloads.append(
            {
                "knowledge_point_id": target["knowledge_point_id"],
                "outcome": outcome,
                "evaluation_method": "parent_manual",
            }
        )
    latest = first_answer
    for offset in range(0, len(remaining_payloads), 30):
        latest = await client.post(
            f"/api/v1/children/{child['id']}/literacy-diagnostic/sessions/{body['id']}/items",
            json={"items": remaining_payloads[offset : offset + 30]},
        )
        assert latest.status_code == 200

    completed = latest.json()
    assert completed["status"] == "completed"
    assert completed["completed_items"] == 120
    result = completed["result"]
    assert result["sample_size"] == 120
    assert result["catalog_size"] == 240
    assert result["directly_known"] == 60
    assert result["uncertain"] == 30
    assert result["unknown"] == 30
    assert result["untested"] == 120
    assert result["estimated_known"] == 120
    assert result["estimation_version"] == LITERACY_DIAGNOSTIC_ESTIMATION_VERSION

    overview = await client.get(
        f"/api/v1/children/{child['id']}/literacy-diagnostic/overview"
    )
    assert overview.status_code == 200
    assert overview.json()["active_session"] is None
    assert overview.json()["latest_result"]["assessment_session_id"] == body["id"]

    history = await client.get(f"/api/v1/children/{child['id']}/literacy-diagnostic/history")
    assert history.status_code == 200
    assert history.json()[0]["directly_known"] == 60

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(LearningRecord)) == 0
        assert await session.scalar(select(func.count()).select_from(AssessmentItem)) == 120
        assert await session.scalar(select(func.count()).select_from(ChildKnowledgeState)) == 120
        estimate = await session.scalar(select(LiteracyEstimate))
        assert estimate is not None
        assert estimate.estimation_version == LITERACY_DIAGNOSTIC_ESTIMATION_VERSION


async def test_diagnostic_rejects_hints_and_cross_family_access(
    test_app,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as owner,
        httpx.AsyncClient(transport=transport, base_url="http://test") as outsider,
    ):
        await register_and_login(owner, "diagnostic-private-owner@example.com")
        _, child = await create_family_and_child(owner, "甲")
        await seed_catalog(session_factory, 120)
        await register_and_login(outsider, "diagnostic-outsider@example.com")

        assert (
            await outsider.get(
                f"/api/v1/children/{child['id']}/literacy-diagnostic/overview"
            )
        ).status_code == 404
        assert (
            await outsider.post(
                f"/api/v1/children/{child['id']}/literacy-diagnostic/start"
            )
        ).status_code == 404

        started = await owner.post(
            f"/api/v1/children/{child['id']}/literacy-diagnostic/start"
        )
        assert started.status_code == 200
        target = started.json()["targets"][0]
        hinted = await owner.post(
            f"/api/v1/children/{child['id']}/literacy-diagnostic/sessions/{started.json()['id']}/items",
            json={
                "items": [
                    {
                        "knowledge_point_id": target["knowledge_point_id"],
                        "outcome": "hinted_correct",
                    }
                ]
            },
        )
        assert hinted.status_code == 422
        hinted_speech = await owner.post(
            f"/api/v1/children/{child['id']}/literacy-diagnostic/sessions/{started.json()['id']}/speech-attempts",
            json={
                "knowledge_point_id": target["knowledge_point_id"],
                "attempt_index": 1,
                "provider": "browser_speech_recognition",
                "decision": "uncertain",
                "hint_used": True,
            },
        )
        assert hinted_speech.status_code == 422
