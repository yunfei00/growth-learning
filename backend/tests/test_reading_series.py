"""Serialized reading keeps one ordered episode per completed reading day."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import DailyReadingStatus, DailyReadingTask
from app.services.review_planning import get_or_create_daily_plan

pytestmark = pytest.mark.anyio
PASSWORD = "reading-series-tests-only"


async def _register_family_child(client: httpx.AsyncClient, suffix: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"series-{suffix}@example.com",
            "display_name": f"连续阅读家长{suffix}",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"email": f"series-{suffix}@example.com", "password": PASSWORD},
        )
    ).status_code == 200
    family = (await client.post("/api/v1/families", json={"name": f"阅读家庭{suffix}"})).json()
    child_response = await client.post(
        f"/api/v1/families/{family['id']}/children",
        json={"display_name": f"阿海读者{suffix}", "birth_date": "2021-06-26"},
    )
    assert child_response.status_code == 201
    return child_response.json()


async def test_series_has_30_ordered_days_and_advances_after_completion(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    child = await _register_family_child(client, "advance")
    child_id = child["id"]

    today = await client.get(f"/api/v1/children/{child_id}/experience/today")
    assert today.status_code == 200
    reading_task = next(item for item in today.json()["tasks"] if item["kind"] == "reading")
    assert "第1天/30天" in reading_task["title"]
    first_version_id = reading_task["href"].rsplit("/", 1)[-1]

    progress = await client.get(f"/api/v1/children/{child_id}/reading-series/current")
    assert progress.status_code == 200
    payload = progress.json()
    assert payload["title"] == "小鱼阿海的大冒险"
    assert payload["total_episodes"] == 30
    assert payload["completed_episodes"] == 0
    assert payload["current_episode_number"] == 1
    assert len(payload["episodes"]) == 30
    assert payload["episodes"][0]["title"] == "沙子里的亮光"
    assert payload["episodes"][0]["paragraphs"]
    assert payload["episodes"][0]["focus_characters"]
    assert payload["episodes"][-1]["title"] == "新的地图亮了起来"
    assert payload["episodes"][-1]["paragraphs"]
    assert payload["episodes"][-1]["story_version_id"] is None

    started = await client.post(
        f"/api/v1/children/{child_id}/story-versions/{first_version_id}/reading/start",
        json={"reading_mode": "independent"},
    )
    assert started.status_code == 200
    reading_session_id = started.json()["id"]
    completed = await client.post(
        f"/api/v1/children/{child_id}/reading-sessions/{reading_session_id}/daily-complete",
        json={"duration_seconds": 30},
    )
    assert completed.status_code == 200

    progress = await client.get(f"/api/v1/children/{child_id}/reading-series/current")
    assert progress.status_code == 200
    payload = progress.json()
    assert payload["completed_episodes"] == 1
    assert payload["current_episode_number"] == 2

    async with session_factory() as session:
        tomorrow = await get_or_create_daily_plan(
            session,
            uuid.UUID(child_id),
            now=datetime.now(UTC) + timedelta(days=1),
        )
    assert "第2天/30天" in (tomorrow.reading.title or "")
    assert tomorrow.reading.story_version_id is not None
    assert str(tomorrow.reading.story_version_id) != first_version_id


async def test_missed_day_keeps_same_episode(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    child = await _register_family_child(client, "missed")
    child_id = child["id"]

    today = await client.get(f"/api/v1/children/{child_id}/experience/today")
    assert today.status_code == 200
    reading_task = next(item for item in today.json()["tasks"] if item["kind"] == "reading")
    first_version_id = reading_task["href"].rsplit("/", 1)[-1]

    async with session_factory() as session:
        tomorrow = await get_or_create_daily_plan(
            session,
            uuid.UUID(child_id),
            now=datetime.now(UTC) + timedelta(days=1),
        )
    assert "第1天/30天" in (tomorrow.reading.title or "")
    assert str(tomorrow.reading.story_version_id) == first_version_id


async def test_read_ahead_can_finish_future_episode_without_skipping_earlier_days(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    child = await _register_family_child(client, "ahead")
    child_id = child["id"]

    today = await client.get(f"/api/v1/children/{child_id}/experience/today")
    assert today.status_code == 200
    reading_task = next(item for item in today.json()["tasks"] if item["kind"] == "reading")
    first_version_id = reading_task["href"].rsplit("/", 1)[-1]

    opened = await client.post(
        f"/api/v1/children/{child_id}/reading-series/current/episodes/10/open"
    )
    assert opened.status_code == 200
    tenth_version_id = opened.json()["story_version_id"]
    assert tenth_version_id != first_version_id

    started = await client.post(
        f"/api/v1/children/{child_id}/story-versions/{tenth_version_id}/reading/start",
        json={"reading_mode": "independent"},
    )
    assert started.status_code == 200
    completed = await client.post(
        f"/api/v1/children/{child_id}/reading-sessions/{started.json()['id']}/daily-complete",
        json={"duration_seconds": 45},
    )
    assert completed.status_code == 200

    progress = await client.get(f"/api/v1/children/{child_id}/reading-series/current")
    assert progress.status_code == 200
    payload = progress.json()
    assert payload["completed_episodes"] == 1
    assert payload["current_episode_number"] == 1
    assert payload["episodes"][9]["status"] == "completed"

    async with session_factory() as session:
        tomorrow = await get_or_create_daily_plan(
            session,
            uuid.UUID(child_id),
            now=datetime.now(UTC) + timedelta(days=1),
        )
    assert "第1天/30天" in (tomorrow.reading.title or "")
    assert str(tomorrow.reading.story_version_id) == first_version_id


async def test_unfinished_legacy_today_task_is_repaired_to_current_series_episode(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    child = await _register_family_child(client, "legacy-repair")
    child_id = child["id"]

    today = await client.get(f"/api/v1/children/{child_id}/experience/today")
    assert today.status_code == 200
    original = next(item for item in today.json()["tasks"] if item["kind"] == "reading")
    first_version_id = original["href"].rsplit("/", 1)[-1]

    manual = await client.post(
        f"/api/v1/children/{child_id}/stories/manual",
        json={
            "title": "旧的临时故事",
            "content": "小猫来到河边。它看见一条小鱼，又慢慢走回家。",
        },
    )
    assert manual.status_code == 201, manual.text
    legacy_version_id = manual.json()["version"]["id"]
    assert legacy_version_id != first_version_id

    async with session_factory() as session:
        task = await session.scalar(
            select(DailyReadingTask).where(DailyReadingTask.child_id == uuid.UUID(child_id))
        )
        assert task is not None
        task.story_version_id = uuid.UUID(legacy_version_id)
        task.status = DailyReadingStatus.IN_PROGRESS
        await session.commit()

    repaired = await client.get(f"/api/v1/children/{child_id}/experience/today")
    assert repaired.status_code == 200
    reading_task = next(item for item in repaired.json()["tasks"] if item["kind"] == "reading")
    assert "第1天/30天" in reading_task["title"]
    assert reading_task["href"].endswith(first_version_id)

    async with session_factory() as session:
        task = await session.scalar(
            select(DailyReadingTask).where(DailyReadingTask.child_id == uuid.UUID(child_id))
        )
        assert task is not None
        assert task.story_version_id == uuid.UUID(first_version_id)
        assert task.status == DailyReadingStatus.PENDING
        assert task.reading_session_id is None
