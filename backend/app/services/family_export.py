"""Portable private family export written incrementally to a ZIP on disk."""

import csv
import hashlib
import io
import json
import tempfile
import uuid
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from anyio import to_thread
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.object_storage import PrivateObjectStorage
from app.models import (
    AssessmentItem,
    AssessmentSession,
    Child,
    ChildKnowledgeState,
    ChildLearningSettings,
    ChildReviewSchedule,
    ExperimentEvidence,
    ExperimentMediaAsset,
    ExperimentSession,
    ExportJob,
    ExportJobStatus,
    Family,
    FamilyMember,
    GrowthBook,
    GrowthBookVersion,
    GrowthEvent,
    GrowthMediaAsset,
    GrowthReport,
    GrowthReportVersion,
    LearningRecord,
    LearningSession,
    LiteracyEstimate,
    ReadingAnswer,
    ReadingQuestion,
    ReadingSession,
    Story,
    StoryGenerationRun,
    StoryKnowledgePoint,
    StoryVersion,
    User,
)

EXPORT_SCHEMA_VERSION = "growth-learning-export-v1"
EXPECTED_JSON_FILES = {
    "family.json",
    "child.json",
    "learning_records.json",
    "assessment_records.json",
    "mastery.json",
    "reading/stories.json",
    "reading/sessions.json",
    "science/experiments.json",
    "growth/events.json",
    "growth/reports.json",
    "growth/books.json",
    "media/manifest.json",
}
FORBIDDEN_MARKERS = {
    "password_hash",
    "session_token",
    "auth_secret",
    "ai_api_key",
    "minio_secret",
    "postgres_password",
    "database_password",
}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _value(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, datetime, date)):
        return value.isoformat() if not isinstance(value, uuid.UUID) else str(value)
    return value


def _record(row: Any, *, exclude: set[str] | None = None) -> dict[str, Any]:
    blocked = exclude or set()
    return {
        column.name: _value(getattr(row, column.name))
        for column in row.__table__.columns
        if column.name not in blocked
    }


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    output = io.StringIO(newline="")
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


async def _all(session: AsyncSession, model: Any, *conditions: Any) -> list[Any]:
    return list((await session.scalars(select(model).where(*conditions))).all())


async def create_family_export(
    session: AsyncSession,
    storage: PrivateObjectStorage,
    *,
    family_id: uuid.UUID,
    child_id: uuid.UUID | None,
    requested_by_user_id: uuid.UUID,
    ttl_seconds: int,
) -> ExportJob:
    job = ExportJob(
        family_id=family_id,
        child_id=child_id,
        requested_by_user_id=requested_by_user_id,
        status=ExportJobStatus.PROCESSING,
        schema_version=EXPORT_SCHEMA_VERSION,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    try:
        family = await session.get(Family, family_id)
        if family is None:
            raise LookupError("Family not found")
        children = await _all(session, Child, Child.family_id == family_id)
        if child_id:
            children = [child for child in children if child.id == child_id]
            if not children:
                raise LookupError("Child not found")
        child_ids = [child.id for child in children]

        members = list(
            (
                await session.execute(
                    select(FamilyMember, User)
                    .join(User, User.id == FamilyMember.user_id)
                    .where(FamilyMember.family_id == family_id)
                )
            ).all()
        )
        learning_sessions = await _all(
            session, LearningSession, LearningSession.child_id.in_(child_ids)
        )
        learning_records = await _all(
            session, LearningRecord, LearningRecord.child_id.in_(child_ids)
        )
        assessment_sessions = await _all(
            session, AssessmentSession, AssessmentSession.child_id.in_(child_ids)
        )
        assessment_items = await _all(
            session, AssessmentItem, AssessmentItem.child_id.in_(child_ids)
        )
        mastery = await _all(
            session, ChildKnowledgeState, ChildKnowledgeState.child_id.in_(child_ids)
        )
        reviews = await _all(
            session, ChildReviewSchedule, ChildReviewSchedule.child_id.in_(child_ids)
        )
        settings = await _all(
            session, ChildLearningSettings, ChildLearningSettings.child_id.in_(child_ids)
        )
        literacy = await _all(session, LiteracyEstimate, LiteracyEstimate.child_id.in_(child_ids))

        stories = await _all(session, Story, Story.child_id.in_(child_ids))
        story_ids = [item.id for item in stories]
        story_versions = (
            await _all(session, StoryVersion, StoryVersion.story_id.in_(story_ids))
            if story_ids
            else []
        )
        story_version_ids = [item.id for item in story_versions]
        generation_runs = await _all(
            session, StoryGenerationRun, StoryGenerationRun.child_id.in_(child_ids)
        )
        story_points = (
            await _all(
                session,
                StoryKnowledgePoint,
                StoryKnowledgePoint.story_version_id.in_(story_version_ids),
            )
            if story_version_ids
            else []
        )
        questions = (
            await _all(
                session, ReadingQuestion, ReadingQuestion.story_version_id.in_(story_version_ids)
            )
            if story_version_ids
            else []
        )
        reading_sessions = await _all(
            session, ReadingSession, ReadingSession.child_id.in_(child_ids)
        )
        reading_session_ids = [item.id for item in reading_sessions]
        answers = (
            await _all(
                session, ReadingAnswer, ReadingAnswer.reading_session_id.in_(reading_session_ids)
            )
            if reading_session_ids
            else []
        )

        experiments = await _all(
            session, ExperimentSession, ExperimentSession.child_id.in_(child_ids)
        )
        experiment_ids = [item.id for item in experiments]
        evidence = (
            await _all(
                session,
                ExperimentEvidence,
                ExperimentEvidence.experiment_session_id.in_(experiment_ids),
            )
            if experiment_ids
            else []
        )
        experiment_media = await _all(
            session, ExperimentMediaAsset, ExperimentMediaAsset.child_id.in_(child_ids)
        )

        events = await _all(session, GrowthEvent, GrowthEvent.child_id.in_(child_ids))
        growth_media = await _all(
            session, GrowthMediaAsset, GrowthMediaAsset.child_id.in_(child_ids)
        )
        reports = await _all(session, GrowthReport, GrowthReport.child_id.in_(child_ids))
        report_ids = [item.id for item in reports]
        report_versions = (
            await _all(session, GrowthReportVersion, GrowthReportVersion.report_id.in_(report_ids))
            if report_ids
            else []
        )
        books = await _all(session, GrowthBook, GrowthBook.child_id.in_(child_ids))
        book_ids = [item.id for item in books]
        book_versions = (
            await _all(session, GrowthBookVersion, GrowthBookVersion.growth_book_id.in_(book_ids))
            if book_ids
            else []
        )

        files: dict[str, bytes] = {
            "family.json": _json_bytes(
                {
                    "family": _record(family),
                    "members": [
                        {
                            "membership_id": str(member.id),
                            "user_id": str(user.id),
                            "role": member.role,
                            "display_name": user.display_name,
                            "email": user.email,
                        }
                        for member, user in members
                    ],
                }
            ),
            "child.json": _json_bytes([_record(item) for item in children]),
            "learning_records.json": _json_bytes(
                {
                    "sessions": [_record(item) for item in learning_sessions],
                    "records": [_record(item) for item in learning_records],
                    "review_schedules": [_record(item) for item in reviews],
                    "settings": [_record(item) for item in settings],
                }
            ),
            "assessment_records.json": _json_bytes(
                {
                    "sessions": [_record(item) for item in assessment_sessions],
                    "items": [_record(item) for item in assessment_items],
                    "literacy_estimates": [_record(item) for item in literacy],
                }
            ),
            "mastery.json": _json_bytes([_record(item) for item in mastery]),
            "reading/stories.json": _json_bytes(
                {
                    "stories": [_record(item) for item in stories],
                    "versions": [_record(item) for item in story_versions],
                    "generation_runs": [_record(item) for item in generation_runs],
                    "knowledge_points": [_record(item) for item in story_points],
                    "questions": [_record(item) for item in questions],
                }
            ),
            "reading/sessions.json": _json_bytes(
                {
                    "sessions": [_record(item) for item in reading_sessions],
                    "answers": [_record(item) for item in answers],
                }
            ),
            "science/experiments.json": _json_bytes(
                {
                    "sessions": [_record(item) for item in experiments],
                    "evidence": [_record(item) for item in evidence],
                }
            ),
            "growth/events.json": _json_bytes([_record(item) for item in events]),
            "growth/reports.json": _json_bytes(
                {
                    "reports": [_record(item) for item in reports],
                    "versions": [_record(item) for item in report_versions],
                }
            ),
            "growth/books.json": _json_bytes(
                {
                    "books": [_record(item) for item in books],
                    "versions": [_record(item) for item in book_versions],
                }
            ),
            "CSV/learning_records.csv": _csv_bytes([_record(item) for item in learning_records]),
            "CSV/assessment_records.csv": _csv_bytes([_record(item) for item in assessment_items]),
        }

        media_entries: list[dict[str, Any]] = []
        media_sources: list[tuple[str, str, str, int, str]] = []
        for asset in [*experiment_media, *growth_media]:
            scope = "science" if isinstance(asset, ExperimentMediaAsset) else "growth"
            archive_path = f"media/{scope}/{asset.id}-{Path(asset.original_filename).name}"
            media_entries.append(
                {
                    "id": str(asset.id),
                    "scope": scope,
                    "archive_path": archive_path,
                    "mime_type": asset.mime_type,
                    "size_bytes": asset.size_bytes,
                    "original_filename": asset.original_filename,
                }
            )
            media_sources.append(
                (archive_path, asset.object_key, asset.mime_type, asset.size_bytes, scope)
            )
        files["media/manifest.json"] = _json_bytes(media_entries)

        record_counts = {
            "children": len(children),
            "learning_records": len(learning_records),
            "assessment_items": len(assessment_items),
            "mastery_states": len(mastery),
            "stories": len(stories),
            "reading_sessions": len(reading_sessions),
            "experiment_sessions": len(experiments),
            "growth_events": len(events),
            "growth_report_versions": len(report_versions),
            "growth_book_versions": len(book_versions),
            "media": len(media_entries),
        }

        with tempfile.TemporaryDirectory(prefix="growth-export-") as temp_dir:
            bundle_path = Path(temp_dir) / f"growth-learning-export-{job.id}.zip"
            file_manifest: list[dict[str, Any]] = []
            with zipfile.ZipFile(
                bundle_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
            ) as archive:
                for path, content in files.items():
                    archive.writestr(path, content)
                    file_manifest.append(
                        {
                            "path": path,
                            "size_bytes": len(content),
                            "sha256": hashlib.sha256(content).hexdigest(),
                        }
                    )
                for archive_path, object_key, mime_type, expected_size, scope in media_sources:
                    del mime_type, scope
                    media_digest = hashlib.sha256()
                    written_size = 0
                    with archive.open(archive_path, "w", force_zip64=True) as target:
                        async for chunk in storage.stream(object_key):
                            target.write(chunk)
                            media_digest.update(chunk)
                            written_size += len(chunk)
                    if written_size != expected_size:
                        raise ValueError("Media size mismatch while building export")
                    file_manifest.append(
                        {
                            "path": archive_path,
                            "size_bytes": written_size,
                            "sha256": media_digest.hexdigest(),
                        }
                    )
                manifest = {
                    "format_version": EXPORT_SCHEMA_VERSION,
                    "generated_at": datetime.now(UTC).isoformat(),
                    "family_id": str(family_id),
                    "child_ids": [str(item) for item in child_ids],
                    "record_counts": record_counts,
                    "files": file_manifest,
                    "media_count": len(media_entries),
                    "media_size_bytes": sum(item[3] for item in media_sources),
                }
                archive.writestr("manifest.json", _json_bytes(manifest))

            await to_thread.run_sync(validate_export_bundle, bundle_path)
            checksum = await to_thread.run_sync(_file_sha256, bundle_path)
            object_key = f"exports/{family_id}/{job.id}.zip"
            await storage.put_file(object_key, bundle_path, "application/zip")
            size_bytes = (await to_thread.run_sync(bundle_path.stat)).st_size

        now = datetime.now(UTC)
        job.status = ExportJobStatus.COMPLETED
        job.object_key = object_key
        job.manifest_snapshot = manifest
        job.size_bytes = size_bytes
        job.checksum_sha256 = checksum
        job.completed_at = now
        job.expires_at = now + timedelta(seconds=ttl_seconds)
        await session.commit()
        await session.refresh(job)
        return job
    except Exception as error:
        await session.rollback()
        current = await session.get(ExportJob, job.id)
        if current is not None:
            current.status = ExportJobStatus.FAILED
            current.failure_reason = str(error)[:240]
            await session.commit()
        raise


def validate_export_bundle(path: Path) -> dict[str, Any]:
    """Validate V1 shape, counts, per-file checksums, and obvious secret-field leakage."""
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "manifest.json" not in names or not EXPECTED_JSON_FILES.issubset(names):
            raise ValueError("Export bundle is missing required files")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format_version") != EXPORT_SCHEMA_VERSION:
            raise ValueError("Unsupported export schema version")
        for entry in manifest.get("files", []):
            digest = hashlib.sha256()
            size_bytes = 0
            with archive.open(entry["path"]) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size_bytes += len(chunk)
            if size_bytes != entry["size_bytes"] or digest.hexdigest() != entry["sha256"]:
                raise ValueError("Export bundle checksum validation failed")
        text_paths = [name for name in names if name.endswith((".json", ".csv"))]
        combined = "\n".join(
            archive.read(name).decode("utf-8-sig", errors="ignore").casefold()
            for name in text_paths
        )
        if any(marker in combined for marker in FORBIDDEN_MARKERS):
            raise ValueError("Export bundle contains a forbidden secret field")
        counts = manifest.get("record_counts", {})
        if counts.get("children") != len(json.loads(archive.read("child.json"))):
            raise ValueError("Export child record count mismatch")
        if counts.get("media") != len(json.loads(archive.read("media/manifest.json"))):
            raise ValueError("Export media record count mismatch")
        return manifest
