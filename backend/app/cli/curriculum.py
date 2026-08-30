"""Curriculum Platform V1 list, validate, export, and idempotent import CLI."""

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from sqlalchemy import select

from app.db.session import session_scope
from app.models import CurriculumRelease, SystemRole, User
from app.schemas.curriculum import CurriculumDocument
from app.services.curriculum import (
    export_curriculum_release,
    import_curriculum_document,
    list_curriculum_releases,
    validate_curriculum_release,
)


async def list_command(args: argparse.Namespace) -> int:
    async with session_scope() as session:
        releases = await list_curriculum_releases(
            session,
            grade_level=args.grade_level,
            semester=args.semester,
            subject=args.subject,
            status=args.status,
        )
        for release in releases:
            print(
                f"{release.id} {release.curriculum_key}@{release.release_version} "
                f"{release.status} grade={release.grade_level or 'foundation'} "
                f"semester={release.semester} subject={release.subject}"
            )
    return 0


async def validate_command(args: argparse.Namespace) -> int:
    async with session_scope() as session:
        release = await session.get(CurriculumRelease, uuid.UUID(args.release_id))
        if release is None:
            raise ValueError("Curriculum release not found")
        report = await validate_curriculum_release(session, release)
        print(report.model_dump_json(indent=2))
        return 0 if report.valid else 1


async def export_command(args: argparse.Namespace) -> int:
    async with session_scope() as session:
        release = await session.get(CurriculumRelease, uuid.UUID(args.release_id))
        if release is None:
            raise ValueError("Curriculum release not found")
        document = await export_curriculum_release(session, release)
    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        await asyncio.to_thread(Path(args.output).write_text, payload, encoding="utf-8")
        print(args.output)
    else:
        print(payload, end="")
    return 0


async def import_command(args: argparse.Namespace) -> int:
    source = await asyncio.to_thread(Path(args.path).read_text, encoding="utf-8")
    raw = json.loads(source)
    document = CurriculumDocument.model_validate(raw)
    async with session_scope() as session:
        actor_id = uuid.UUID(int=0)
        if not args.dry_run:
            query = select(User).where(User.system_role == SystemRole.ADMIN)
            if args.actor_email:
                query = query.where(User.email == args.actor_email.lower())
            actor = await session.scalar(query.order_by(User.created_at).limit(1))
            if actor is None:
                raise ValueError("A system admin is required for a real import")
            actor_id = actor.id
        report = await import_curriculum_document(session, document, actor_id, dry_run=args.dry_run)
        print(report.model_dump_json(indent=2))
        return 1 if report.errors else 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Manage Growth Learning curriculum releases")
    subparsers = root.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser("list")
    listing.add_argument("--grade-level", type=int, choices=range(1, 10))
    listing.add_argument("--semester", choices=["full_year", "semester_1", "semester_2"])
    listing.add_argument("--subject", choices=["chinese", "math", "english", "science"])
    listing.add_argument("--status", choices=["draft", "in_review", "published", "archived"])

    validate = subparsers.add_parser("validate")
    validate.add_argument("--release-id", required=True)

    export = subparsers.add_parser("export")
    export.add_argument("--release-id", required=True)
    export.add_argument("--output")

    importing = subparsers.add_parser("import")
    importing.add_argument("path")
    importing.add_argument("--dry-run", action="store_true")
    importing.add_argument("--actor-email")
    return root


def main() -> int:
    args = parser().parse_args()
    handlers = {
        "list": list_command,
        "validate": validate_command,
        "export": export_command,
        "import": import_command,
    }
    try:
        return asyncio.run(handlers[args.command](args))
    except (ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
