"""Server-side English Foundation V1 catalog import."""

import argparse
import asyncio

from app.db.session import session_scope
from app.services.english_catalog import import_english_foundation


async def import_foundation() -> int:
    async with session_scope() as session:
        result = await import_english_foundation(session)
    print(
        f"catalog_version={result.catalog_version} catalog_size={result.catalog_size} "
        f"letters={result.letter_count} words={result.word_count} "
        f"phonics={result.phonics_count} phrases={result.phrase_count} "
        f"practice_items={result.practice_item_count} created={result.created} "
        f"updated={result.updated} skipped={result.skipped} "
        f"practice_items_created={result.practice_items_created} "
        f"course_created={result.course_created} errors={len(result.errors)}"
    )
    return 1 if result.errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the English Foundation catalog")
    parser.add_argument("command", choices=["import-foundation"])
    args = parser.parse_args()
    if args.command == "import-foundation":
        return asyncio.run(import_foundation())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
