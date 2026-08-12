"""Rebuild derived child mastery projections from raw evidence."""

import argparse
import asyncio
import uuid

from app.db.session import session_scope
from app.services.mastery import recompute_child_states


async def run(child_id: uuid.UUID | None) -> int:
    async with session_scope() as session:
        count = await recompute_child_states(session, child_id)
    print(f"Mastery recompute completed: states={count} algorithm=v1")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild derived mastery from preserved evidence")
    parser.add_argument("--child-id", type=uuid.UUID)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.child_id)))


if __name__ == "__main__":
    main()
