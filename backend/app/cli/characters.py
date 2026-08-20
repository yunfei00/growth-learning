"""Server-side Chinese-character catalog import commands."""

import argparse
import asyncio

from app.db.session import session_scope
from app.services.character_catalog import (
    import_characters,
    import_expanded_catalog,
    import_starter_relations,
    load_starter_dataset,
)


async def import_starter() -> int:
    async with session_scope() as session:
        result = await import_characters(session, load_starter_dataset())
        relations = await import_starter_relations(session) if not result.errors else None
    print(
        f"created={result.created} updated={result.updated} "
        f"skipped={result.skipped} errors={len(result.errors)}"
    )
    if relations is not None:
        print(
            f"relations_created={relations.created} "
            f"relations_skipped={relations.skipped} errors={len(relations.errors)}"
        )
    return 1 if result.errors or (relations and relations.errors) else 0


async def import_catalog() -> int:
    async with session_scope() as session:
        result = await import_expanded_catalog(session)
    print(
        f"catalog_version={result.catalog_version} catalog_size={result.catalog_size} "
        f"created={result.created} updated={result.updated} skipped={result.skipped} "
        f"preserved={result.preserved} course_created={result.course_created} "
        f"errors={len(result.errors)}"
    )
    return 1 if result.errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the Chinese-character catalog")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("import-starter")
    commands.add_parser("import-chinese-catalog")
    args = parser.parse_args()
    if args.command == "import-starter":
        return asyncio.run(import_starter())
    if args.command == "import-chinese-catalog":
        return asyncio.run(import_catalog())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
