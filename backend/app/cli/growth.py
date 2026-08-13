"""Safe maintenance commands for derived growth events and expired exports."""

import argparse
import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import session_scope
from app.integrations.object_storage import build_private_object_storage
from app.models import Child, ExportJob, ExportJobStatus
from app.services.growth_timeline import project_growth_events


async def rebuild(child_id: uuid.UUID | None) -> int:
    async with session_scope() as session:
        child_ids = (
            [child_id] if child_id else list((await session.scalars(select(Child.id))).all())
        )
        created = existing = 0
        for current_child_id in child_ids:
            result = await project_growth_events(session, current_child_id)
            created += result.created
            existing += result.existing
    print(
        "Growth event rebuild completed: "
        f"children={len(child_ids)} created={created} existing={existing}"
    )
    return 0


async def cleanup_exports() -> int:
    storage = build_private_object_storage()
    async with session_scope() as session:
        jobs = list(
            (
                await session.scalars(
                    select(ExportJob).where(
                        ExportJob.status == ExportJobStatus.COMPLETED,
                        ExportJob.expires_at <= datetime.now(UTC),
                    )
                )
            ).all()
        )
        for job in jobs:
            if job.object_key:
                await storage.remove(job.object_key)
            job.status = ExportJobStatus.EXPIRED
            job.object_key = None
        await session.commit()
    print(f"Expired export cleanup completed: expired={len(jobs)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Growth archive maintenance")
    commands = parser.add_subparsers(dest="command", required=True)
    rebuild_parser = commands.add_parser("rebuild-growth-events")
    rebuild_parser.add_argument("--child-id", type=uuid.UUID)
    commands.add_parser("cleanup-exports")
    return parser


async def run(args: argparse.Namespace) -> int:
    return (
        await rebuild(args.child_id)
        if args.command == "rebuild-growth-events"
        else await cleanup_exports()
    )


def main() -> None:
    raise SystemExit(asyncio.run(run(build_parser().parse_args())))


if __name__ == "__main__":
    main()
