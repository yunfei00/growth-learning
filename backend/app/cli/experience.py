"""Rebuild deterministic child achievements and positive encouragement entries."""

import argparse
import asyncio
import uuid

from sqlalchemy import select

from app.db.session import session_scope
from app.models import Child
from app.services.child_experience import rebuild_child_achievements


async def rebuild(child_id: uuid.UUID | None) -> int:
    async with session_scope() as session:
        children = (
            [await session.get(Child, child_id)]
            if child_id
            else list((await session.scalars(select(Child).order_by(Child.created_at))).all())
        )
        children = [child for child in children if child is not None]
        created = existing = rewards = 0
        for child in children:
            result = await rebuild_child_achievements(session, child)
            created += result.created
            existing += result.existing
            rewards += result.rewards_created
    print(
        "Achievement rebuild completed: "
        f"children={len(children)} created={created} existing={existing} rewards={rewards}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Child experience maintenance")
    commands = parser.add_subparsers(dest="command", required=True)
    rebuild_parser = commands.add_parser("rebuild-achievements")
    rebuild_parser.add_argument("--child-id", type=uuid.UUID)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(asyncio.run(rebuild(args.child_id)))


if __name__ == "__main__":
    main()
