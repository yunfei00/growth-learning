"""Server-side Chinese-character catalog import commands."""

import argparse
import asyncio

from app.db.session import session_scope
from app.services.character_catalog import (
    import_characters,
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the Chinese-character catalog")
    parser.add_subparsers(dest="command", required=True).add_parser("import-starter")
    args = parser.parse_args()
    if args.command == "import-starter":
        return asyncio.run(import_starter())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
