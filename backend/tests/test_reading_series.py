"""Serialized reading keeps one ordered episode per completed reading day."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
    assert payload["episodes"][-1]["title"] == "新的地图亮了起来"

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
