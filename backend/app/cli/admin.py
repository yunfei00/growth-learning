"""Provision and maintain system administrators without password arguments."""

import argparse
import asyncio
import getpass
import sys

from app.db.session import session_scope
from app.services.admin_provisioning import create_admin, promote_admin, set_admin_password


def read_password() -> str:
    password = (
        getpass.getpass("Password: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\r\n")
    )
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters")
    return password


async def run(args: argparse.Namespace) -> int:
    async with session_scope() as session:
        if args.command == "create-admin":
            result = await create_admin(
                session,
                email=args.email,
                display_name=args.display_name,
                password=read_password(),
            )
        elif args.command == "promote-admin":
            result = await promote_admin(session, email=args.email)
        else:
            result = await set_admin_password(session, email=args.email, password=read_password())
    print(f"Admin operation completed: {result.action} ({result.user.email})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Growth Learning system admin management")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-admin")
    create.add_argument("--email", required=True)
    create.add_argument("--display-name", required=True)

    promote = subparsers.add_parser("promote-admin")
    promote.add_argument("--email", required=True)

    set_password = subparsers.add_parser("set-password")
    set_password.add_argument("--email", required=True)
    return parser


def main() -> None:
    try:
        raise SystemExit(asyncio.run(run(build_parser().parse_args())))
    except (LookupError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
