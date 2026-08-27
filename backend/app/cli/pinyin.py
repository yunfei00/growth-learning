"""Server-side Pinyin foundation catalog import."""

import argparse
import asyncio

from app.db.session import session_scope
from app.services.pinyin_catalog import import_pinyin_foundation


async def import_foundation() -> int:
    async with session_scope() as session:
        result = await import_pinyin_foundation(session)
    print(
        f"catalog_version={result.catalog_version} catalog_size={result.catalog_size} "
        f"created={result.created} updated={result.updated} skipped={result.skipped} "
        f"relations_created={result.relations_created} "
        f"practices_created={result.practices_created} "
        f"course_created={result.course_created} errors={len(result.errors)}"
    )
    return 1 if result.errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the Pinyin foundation catalog")
    parser.add_argument("command", choices=["import-foundation"])
    args = parser.parse_args()
    if args.command == "import-foundation":
        return asyncio.run(import_foundation())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
