"""Idempotent server-side commands for the Weekend Science Lab catalog."""

import argparse
import asyncio

from app.db.session import session_scope
from app.services.science_catalog import import_starter_science_experiments


async def import_starter() -> int:
    async with session_scope() as session:
        result = await import_starter_science_experiments(session)
    print(
        f"created={result.created} updated={result.updated} "
        f"skipped={result.skipped} materials_created={result.materials_created} "
        f"errors={len(result.errors)}"
    )
    for error in result.errors:
        print(f"error={error}")
    return 1 if result.errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the Weekend Science Lab catalog")
    parser.add_subparsers(dest="command", required=True).add_parser("import-starter")
    args = parser.parse_args()
    if args.command == "import-starter":
        return asyncio.run(import_starter())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
