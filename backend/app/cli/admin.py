"""Provision and maintain system administrators without password arguments."""

import argparse
import asyncio
import getpass
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import session_scope
from app.models import AccountStatus, User
from app.services.admin_provisioning import (
    create_admin,
    promote_admin,
    reset_user_password,
    set_admin_password,
)
from app.services.platform_access import (
    create_platform_invitation,
    list_admin_users,
    set_user_account_status,
)


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
        elif args.command == "set-password":
            result = await set_admin_password(session, email=args.email, password=read_password())
        elif args.command == "reset-password":
            result = await reset_user_password(session, email=args.email, password=read_password())
        elif args.command == "list-users":
            users = await list_admin_users(
                session,
                search=args.search,
                account_status=args.status,
                page=1,
                page_size=100,
            )
            for item in users.items:
                print(
                    f"{item.user.email}\t{item.user.display_name}\t"
                    f"{item.user.account_status}\t{item.user.system_role}\t"
                    f"families={item.family_count}"
                )
            print(f"Users listed: {len(users.items)} of {users.total}")
            return 0
        elif args.command in {"activate-user", "suspend-user"}:
            user = await session.scalar(select(User).where(User.email == args.email.casefold()))
            if user is None:
                raise LookupError("User not found")
            new_status = (
                AccountStatus.ACTIVE if args.command == "activate-user" else AccountStatus.SUSPENDED
            )
            await set_user_account_status(
                session,
                target=user,
                new_status=new_status,
                actor_user_id=None,
            )
            print(f"User status updated: {user.email} ({new_status})")
            return 0
        elif args.command == "create-invitation":
            actor = await session.scalar(
                select(User).where(User.email == args.created_by_email.casefold())
            )
            if (
                actor is None
                or actor.system_role != "admin"
                or actor.account_status != AccountStatus.ACTIVE
            ):
                raise LookupError("Active system administrator not found")
            result = await create_platform_invitation(
                session,
                get_settings(),
                actor=actor,
                expires_at=datetime.now(UTC) + timedelta(days=args.expires_days),
                max_uses=args.max_uses,
                email_constraint=args.email,
            )
            print(f"Invitation created (shown once): {result.plaintext_code}")
            return 0
        else:  # pragma: no cover - argparse prevents this branch
            raise ValueError("Unknown command")
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
    reset_password = subparsers.add_parser("reset-password")
    reset_password.add_argument("--email", required=True)

    list_users = subparsers.add_parser("list-users")
    list_users.add_argument("--search")
    list_users.add_argument("--status", choices=["active", "suspended", "disabled"])

    activate = subparsers.add_parser("activate-user")
    activate.add_argument("--email", required=True)
    suspend = subparsers.add_parser("suspend-user")
    suspend.add_argument("--email", required=True)

    invitation = subparsers.add_parser("create-invitation")
    invitation.add_argument("--created-by-email", required=True)
    invitation.add_argument("--expires-days", type=int, default=7)
    invitation.add_argument("--max-uses", type=int, default=1)
    invitation.add_argument("--email")
    return parser


def main() -> None:
    try:
        raise SystemExit(asyncio.run(run(build_parser().parse_args())))
    except (LookupError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
