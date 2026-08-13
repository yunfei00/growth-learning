"""Rebuild deterministic review schedules without altering raw evidence."""

import argparse
import asyncio
import uuid

from app.db.session import session_scope
from app.services.review_planning import (
    REVIEW_ALGORITHM_VERSION,
    recompute_child_review_schedules,
)


async def run(child_id: uuid.UUID | None) -> int:
    async with session_scope() as session:
        count = await recompute_child_review_schedules(session, child_id)
    print(
        f"Review schedule recompute completed: schedules={count} "
        f"algorithm={REVIEW_ALGORITHM_VERSION}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild review schedules from preserved learning and assessment evidence"
    )
    parser.add_argument("--child-id", type=uuid.UUID)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.child_id)))


if __name__ == "__main__":
    main()
