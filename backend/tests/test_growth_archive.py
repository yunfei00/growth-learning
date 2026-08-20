"""Unified growth archive, immutable reports/books, export, and privacy tests."""

import io
import json
import uuid
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from anyio import to_thread
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.growth import get_growth_storage
from app.integrations.ai.fake import FakeAIProvider
from app.integrations.object_storage import PrivateObjectStorage
from app.models import (
    ChildKnowledgeState,
    ExperimentSession,
    ExperimentStep,
    ExportJob,
    FamilyMember,
    FamilyRole,
    GrowthBookVersion,
    GrowthEvent,
    GrowthReportVersion,
    KnowledgePoint,
    LearningRecord,
    LearningSession,
    ScienceExperiment,
    ScienceExperimentVersion,
    SystemRole,
    User,
)
from app.schemas.growth import GrowthReportGenerate
from app.services.growth_reports import generate_growth_report
from app.services.growth_timeline import project_growth_events

pytestmark = pytest.mark.anyio
PASSWORD = "growth-archive-tests-only"


class FakeGrowthStorage(PrivateObjectStorage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, object_key: str, content: bytes, mime_type: str) -> None:
        del mime_type
        self.objects[object_key] = content

    async def put_file(self, object_key: str, path: Path, mime_type: str) -> None:
        del mime_type
        self.objects[object_key] = await to_thread.run_sync(path.read_bytes)

    async def read(self, object_key: str) -> bytes:
        return self.objects[object_key]

    async def stream(self, object_key: str, chunk_size: int = 1024 * 1024) -> AsyncIterator[bytes]:
        content = self.objects[object_key]
        for index in range(0, len(content), chunk_size):
            yield content[index : index + chunk_size]

    async def remove(self, object_key: str) -> None:
        self.objects.pop(object_key, None)


async def register(client: httpx.AsyncClient, email: str, name: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": name, "password": PASSWORD},
    )
    assert response.status_code == 201
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    return response.json()


async def test_growth_archive_reports_books_export_and_privacy(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    storage = FakeGrowthStorage()
    test_app.dependency_overrides[get_growth_storage] = lambda: storage
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent,
        httpx.AsyncClient(transport=transport, base_url="http://test") as companion,
        httpx.AsyncClient(transport=transport, base_url="http://test") as outsider,
        httpx.AsyncClient(transport=transport, base_url="http://test") as system_admin,
    ):
        parent_user = await register(parent, "growth-parent@example.com", "成长记录家长")
        family = (await parent.post("/api/v1/families", json={"name": "成长档案家庭"})).json()
        child = (
            await parent.post(
                f"/api/v1/families/{family['id']}/children",
                json={"display_name": "小小记录者", "birth_date": "2020-05-01"},
            )
        ).json()
        companion_user = await register(companion, "growth-companion@example.com", "成长陪伴者")
        await register(outsider, "growth-outsider@example.com", "其他家庭成员")
        admin_user = await register(system_admin, "growth-system@example.com", "平台管理员")

        async with session_factory() as session:
            session.add(
                FamilyMember(
                    family_id=uuid.UUID(family["id"]),
                    user_id=uuid.UUID(companion_user["id"]),
                    role=FamilyRole.COMPANION,
                )
            )
            admin = await session.get(User, uuid.UUID(admin_user["id"]))
            assert admin is not None
            admin.system_role = SystemRole.ADMIN

            experiment = ScienceExperiment(
                canonical_key="growth_archive_bridge",
                title="纸桥成长实验",
                description="观察纸张折叠后的承重变化。",
                age_min=4,
                age_max=9,
                difficulty="intro",
                estimated_duration_minutes=20,
                guiding_question="怎样让纸桥更结实？",
                expected_phenomenon="折叠后承重增加。",
                child_friendly_explanation="折痕像小脚一样支撑纸桥。",
                parent_scientific_explanation="截面改变提高抗弯刚度。",
                safety_notes=[],
                common_failure_reasons=[],
                follow_up_questions=[],
                likely_child_questions=[],
                steps=["折纸", "承重"],
                status="enabled",
                source_type="system",
            )
            session.add(experiment)
            await session.flush()
            version = ScienceExperimentVersion(
                experiment_id=experiment.id,
                version_number=1,
                snapshot={
                    "title": experiment.title,
                    "guiding_question": experiment.guiding_question,
                },
            )
            session.add(version)
            await session.flush()
            moment = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)
            session.add(
                ExperimentSession(
                    child_id=uuid.UUID(child["id"]),
                    experiment_id=experiment.id,
                    experiment_version_id=version.id,
                    experiment_snapshot=version.snapshot,
                    accompanying_user_id=uuid.UUID(parent_user["id"]),
                    request_key="growth-archive-science-1",
                    status="completed",
                    current_step=ExperimentStep.COMPLETE,
                    local_date=date(2026, 8, 13),
                    timezone="Asia/Shanghai",
                    started_at=moment,
                    completed_at=moment + timedelta(minutes=20),
                )
            )
            await session.commit()

        exact_text = "今天第一次自己认出了路牌上的‘银行’，还回头告诉了我。"
        manual = await parent.post(
            f"/api/v1/children/{child['id']}/growth/events",
            json={
                "occurred_at": "2026-08-13T10:00:00+08:00",
                "title": "第一次认出路牌",
                "text": exact_text,
                "event_type": "manual_growth_note",
                "category": "learning",
            },
        )
        assert manual.status_code == 201
        assert manual.json()["body"] == exact_text
        media = await parent.post(
            f"/api/v1/children/{child['id']}/growth/events/{manual.json()['id']}/media",
            files={"file": ("moment.jpg", b"\xff\xd8\xffprivate-growth-image", "image/jpeg")},
        )
        assert media.status_code == 201
        content_url = media.json()["media"][0]["content_url"]
        assert (await companion.get(content_url)).content == b"\xff\xd8\xffprivate-growth-image"
        assert (await outsider.get(content_url)).status_code == 404

        first_rebuild = await parent.post(f"/api/v1/children/{child['id']}/growth/rebuild")
        second_rebuild = await parent.post(f"/api/v1/children/{child['id']}/growth/rebuild")
        assert first_rebuild.status_code == 200
        assert first_rebuild.json()["created"] == 1
        assert second_rebuild.json()["created"] == 0
        assert second_rebuild.json()["existing"] == 1

        timeline = await companion.get(f"/api/v1/children/{child['id']}/growth/events")
        assert timeline.status_code == 200
        assert timeline.json()["total"] == 2
        assert exact_text in [item["body"] for item in timeline.json()["items"]]
        science_event = next(
            item for item in timeline.json()["items"] if item["source_type"] == "system"
        )
        assert science_event["source_url"] == (
            f"/science/session/{science_event['source_entity_id']}"
        )
        assert (
            await companion.post(
                f"/api/v1/children/{child['id']}/growth/events",
                json={
                    "occurred_at": "2026-08-13T11:00:00+08:00",
                    "text": "陪伴者原样记录：孩子主动解释了纸桥。",
                    "event_type": "family_observation",
                    "category": "science",
                },
            )
        ).status_code == 201
        assert (
            await outsider.get(f"/api/v1/children/{child['id']}/growth/events")
        ).status_code == 404
        assert (
            await system_admin.get(f"/api/v1/children/{child['id']}/growth/events")
        ).status_code == 404

        report_payload = {
            "period_type": "monthly",
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "include_ai_narrative": True,
        }
        report_v1 = await parent.post(
            f"/api/v1/children/{child['id']}/growth/reports", json=report_payload
        )
        report_v2 = await parent.post(
            f"/api/v1/children/{child['id']}/growth/reports", json=report_payload
        )
        assert report_v1.status_code == 201
        assert report_v1.json()["version_number"] == 1
        assert report_v1.json()["metrics"]["science"]["experiments_completed"] == 1
        assert "尚无正式识字检测" in report_v1.json()["sections"]["learning"]
        assert report_v1.json()["ai_narrative"] is None
        assert report_v2.json()["version_number"] == 2
        yearly = await parent.post(
            f"/api/v1/children/{child['id']}/growth/reports",
            json={
                "period_type": "yearly",
                "period_start": "2026-01-01",
                "period_end": "2026-12-31",
            },
        )
        custom = await parent.post(
            f"/api/v1/children/{child['id']}/growth/reports",
            json={
                "period_type": "custom",
                "period_start": "2026-08-10",
                "period_end": "2026-08-15",
            },
        )
        assert yearly.status_code == 201 and yearly.json()["period_type"] == "yearly"
        assert custom.status_code == 201 and custom.json()["period_type"] == "custom"
        assert (
            await companion.get(f"/api/v1/children/{child['id']}/growth/reports")
        ).status_code == 403

        event_ids = [item["id"] for item in timeline.json()["items"]]
        book_payload = {
            "edition_type": "yearly",
            "edition_key": "2026",
            "title": "《2026 成长册》",
            "selected_event_ids": event_ids,
            "selected_media": [{"kind": "growth", "id": media.json()["media"][0]["id"]}],
            "parent_message": "愿你一直保留好奇心。",
        }
        book_v1 = await parent.post(
            f"/api/v1/children/{child['id']}/growth/books", json=book_payload
        )
        book_v2 = await parent.post(
            f"/api/v1/children/{child['id']}/growth/books", json=book_payload
        )
        assert book_v1.status_code == 201, book_v1.text
        assert book_v1.json()["parent_message"] == "愿你一直保留好奇心。"
        assert book_v2.json()["version_number"] == 2

        assert (
            await companion.post(f"/api/v1/families/{family['id']}/exports", json={})
        ).status_code == 403
        assert (
            await outsider.post(f"/api/v1/families/{family['id']}/exports", json={})
        ).status_code == 404
        assert (
            await system_admin.post(f"/api/v1/families/{family['id']}/exports", json={})
        ).status_code == 404

        exported = await parent.post(f"/api/v1/families/{family['id']}/exports", json={})
        assert exported.status_code == 201, exported.text
        job = exported.json()
        assert job["status"] == "completed"
        downloaded = await parent.get(job["download_url"])
        assert downloaded.status_code == 200
        with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["format_version"] == "growth-learning-export-v1"
            assert manifest["record_counts"]["growth_events"] == 3
            assert "growth/events.json" in archive.namelist()
            exported_text = "\n".join(
                archive.read(name).decode("utf-8-sig", errors="ignore")
                for name in archive.namelist()
                if name.endswith((".json", ".csv"))
            ).casefold()
            assert exact_text in exported_text
            assert "password_hash" not in exported_text
            assert "auth_secret" not in exported_text
            assert "ai_api_key" not in exported_text
            assert PASSWORD.casefold() not in exported_text

        async with session_factory() as session:
            saved_v1 = await session.get(GrowthReportVersion, uuid.UUID(report_v1.json()["id"]))
            saved_book_v1 = await session.get(GrowthBookVersion, uuid.UUID(book_v1.json()["id"]))
            assert saved_v1 is not None and saved_v1.version_number == 1
            assert (
                saved_book_v1 is not None and saved_book_v1.parent_message == "愿你一直保留好奇心。"
            )
            manual_event = await session.get(GrowthEvent, uuid.UUID(manual.json()["id"]))
            assert manual_event is not None and manual_event.body == exact_text

            ai_version = await generate_growth_report(
                session,
                child_id=uuid.UUID(child["id"]),
                actor_user_id=uuid.UUID(parent_user["id"]),
                payload=GrowthReportGenerate(**report_payload),
                provider=FakeAIProvider(
                    ['{"narrative":"这个月保留了一次真实科学探索和家庭成长瞬间。"}']
                ),
            )
            assert ai_version.ai_narrative is not None
            assert ai_version.metrics_snapshot["science"]["experiments_completed"] == 1

            export_job = await session.get(ExportJob, uuid.UUID(job["id"]))
            assert export_job is not None
            export_job.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()
        assert (await parent.get(job["download_url"])).status_code == 410

        async with session_factory() as session:
            learning_session = LearningSession(
                child_id=uuid.UUID(child["id"]),
                actor_user_id=uuid.UUID(parent_user["id"]),
                status="completed",
                source="milestone_test",
                completed_at=datetime(2026, 8, 14, tzinfo=UTC),
            )
            session.add(learning_session)
            await session.flush()
            for index in range(100):
                point = KnowledgePoint(
                    type="chinese_character",
                    status="active",
                    title=f"里程碑字{index}",
                    canonical_key=f"growth-milestone-{index}",
                    source_type="test",
                )
                session.add(point)
                await session.flush()
                session.add(
                    LearningRecord(
                        session_id=learning_session.id,
                        child_id=uuid.UUID(child["id"]),
                        knowledge_point_id=point.id,
                        actor_user_id=uuid.UUID(parent_user["id"]),
                        activity_type="introduced",
                        source="milestone_test",
                        learned_at=datetime(2026, 8, 14, tzinfo=UTC),
                    )
                )
                session.add(
                    ChildKnowledgeState(
                        child_id=uuid.UUID(child["id"]),
                        knowledge_point_id=point.id,
                        mastery_level="stable",
                        mastery_score=1,
                    )
                )
            await session.commit()
            milestone_first = await project_growth_events(session, uuid.UUID(child["id"]))
            milestone_second = await project_growth_events(session, uuid.UUID(child["id"]))
            assert milestone_first.created == 2
            assert milestone_second.created == 0
            milestone_titles = set(
                (
                    await session.scalars(
                        select(GrowthEvent.title).where(
                            GrowthEvent.child_id == uuid.UUID(child["id"])
                        )
                    )
                ).all()
            )
            assert "第一次接触 100 个汉字" in milestone_titles
            assert "稳定掌握达到 100 个汉字" in milestone_titles

    test_app.dependency_overrides.pop(get_growth_storage, None)
