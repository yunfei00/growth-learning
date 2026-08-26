"""Safely remove one explicitly confirmed test household and all owned descendants."""

from __future__ import annotations

import argparse
import asyncio
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass

from sqlalchemy import ForeignKey, Table, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.integrations.object_storage import build_private_object_storage
from app.models import Base, Child, Family, FamilyMember, PlatformAuditLog, User

OBJECT_STORAGE_COLUMNS = frozenset({"object_key", "avatar_key"})


class HouseholdCleanupError(RuntimeError):
    """Raised when a cleanup target cannot be proven safe."""


@dataclass(frozen=True)
class KeptUser:
    id: uuid.UUID
    display_name: str
    email: str


@dataclass(frozen=True)
class TargetChild:
    id: uuid.UUID
    display_name: str
    nickname: str | None


@dataclass(frozen=True)
class CleanupPlan:
    family_id: uuid.UUID
    family_name: str
    members: tuple[KeptUser, ...]
    children: tuple[TargetChild, ...]
    row_ids: dict[str, frozenset[object]]
    object_keys: frozenset[str]

    @property
    def table_counts(self) -> dict[str, int]:
        return {name: len(ids) for name, ids in sorted(self.row_ids.items()) if ids}


@dataclass(frozen=True)
class MediaCleanupResult:
    candidates: int
    removed: int
    retained_referenced: int
    retained_on_error: int


def _single_primary_key(table: Table):
    columns = list(table.primary_key.columns)
    if len(columns) != 1:
        raise HouseholdCleanupError(
            f"Cleanup only supports single-column primary keys; {table.name} has {len(columns)}"
        )
    return columns[0]


def _incoming_foreign_keys() -> dict[str, list[tuple[Table, ForeignKey]]]:
    incoming: dict[str, list[tuple[Table, ForeignKey]]] = defaultdict(list)
    for table in Base.metadata.tables.values():
        _single_primary_key(table)
        for foreign_key in table.foreign_keys:
            if len(foreign_key.constraint.elements) != 1:
                raise HouseholdCleanupError(
                    f"Composite foreign key {foreign_key.constraint.name} is not supported"
                )
            incoming[foreign_key.column.table.name].append((table, foreign_key))
    return incoming


async def _discover_owned_rows(
    session: AsyncSession, family_id: uuid.UUID
) -> dict[str, set[object]]:
    """Follow every incoming FK from one Family without traversing outward to shared rows."""
    family_table = Base.metadata.tables["families"]
    discovered: dict[str, set[object]] = defaultdict(set)
    discovered[family_table.name].add(family_id)
    queue: deque[tuple[str, set[object]]] = deque([(family_table.name, {family_id})])
    incoming = _incoming_foreign_keys()

    while queue:
        parent_name, new_parent_ids = queue.popleft()
        for child_table, foreign_key in incoming.get(parent_name, []):
            child_pk = _single_primary_key(child_table)
            rows = set(
                (
                    await session.scalars(
                        select(child_pk).where(foreign_key.parent.in_(new_parent_ids))
                    )
                ).all()
            )
            unseen = rows - discovered[child_table.name]
            if unseen:
                discovered[child_table.name].update(unseen)
                queue.append((child_table.name, unseen))

    if "users" in discovered:
        raise HouseholdCleanupError("User rows must never enter a household cleanup plan")
    return dict(discovered)


async def _assert_ownership_boundary(
    session: AsyncSession,
    *,
    family_id: uuid.UUID,
    row_ids: dict[str, set[object]],
) -> None:
    target_children = row_ids.get("children", set())
    for table_name, ids in row_ids.items():
        if not ids:
            continue
        table = Base.metadata.tables[table_name]
        primary_key = _single_primary_key(table)
        owner_columns = [
            column
            for name in ("family_id", "child_id")
            if (column := table.c.get(name)) is not None
        ]
        if not owner_columns:
            continue
        rows = (await session.execute(select(*owner_columns).where(primary_key.in_(ids)))).all()
        for row in rows:
            values = dict(zip((column.name for column in owner_columns), row, strict=True))
            row_family_id = values.get("family_id")
            row_child_id = values.get("child_id")
            if row_family_id is not None and row_family_id != family_id:
                raise HouseholdCleanupError(
                    f"Cross-family reference discovered in {table_name}; cleanup aborted"
                )
            if row_child_id is not None and row_child_id not in target_children:
                raise HouseholdCleanupError(
                    f"Cross-child reference discovered in {table_name}; cleanup aborted"
                )


async def _collect_object_keys(
    session: AsyncSession, row_ids: dict[str, set[object]]
) -> frozenset[str]:
    keys: set[str] = set()
    for table_name, ids in row_ids.items():
        table = Base.metadata.tables[table_name]
        primary_key = _single_primary_key(table)
        for column_name in OBJECT_STORAGE_COLUMNS:
            object_key = table.c.get(column_name)
            if object_key is None or not ids:
                continue
            keys.update(
                value
                for value in (
                    await session.scalars(
                        select(object_key).where(primary_key.in_(ids), object_key.is_not(None))
                    )
                ).all()
                if value
            )
    return frozenset(keys)


async def build_cleanup_plan(
    session: AsyncSession, family_id: uuid.UUID, *, lock: bool = False
) -> CleanupPlan:
    family_query = select(Family).where(Family.id == family_id)
    if lock:
        family_query = family_query.with_for_update()
    family = await session.scalar(family_query)
    if family is None:
        raise HouseholdCleanupError(f"Family {family_id} does not exist")

    members = tuple(
        KeptUser(user.id, user.display_name, user.email)
        for user in (
            await session.scalars(
                select(User)
                .join(FamilyMember, FamilyMember.user_id == User.id)
                .where(FamilyMember.family_id == family_id)
                .order_by(FamilyMember.created_at, User.id)
            )
        ).all()
    )
    children = tuple(
        TargetChild(child.id, child.display_name, child.nickname)
        for child in (
            await session.scalars(
                select(Child)
                .where(Child.family_id == family_id)
                .order_by(Child.created_at, Child.id)
            )
        ).all()
    )
    row_ids = await _discover_owned_rows(session, family_id)
    await _assert_ownership_boundary(session, family_id=family_id, row_ids=row_ids)
    object_keys = await _collect_object_keys(session, row_ids)
    return CleanupPlan(
        family_id=family.id,
        family_name=family.name,
        members=members,
        children=children,
        row_ids={name: frozenset(ids) for name, ids in row_ids.items()},
        object_keys=object_keys,
    )


def _deletion_order(row_ids: dict[str, frozenset[object]]) -> list[str]:
    """Return dependent tables before the parent tables they reference."""
    nodes = {name for name, ids in row_ids.items() if ids}
    outgoing: dict[str, set[str]] = {name: set() for name in nodes}
    indegree = {name: 0 for name in nodes}
    for child_name in nodes:
        table = Base.metadata.tables[child_name]
        for foreign_key in table.foreign_keys:
            parent_name = foreign_key.column.table.name
            if parent_name not in nodes or parent_name == child_name:
                continue
            if parent_name not in outgoing[child_name]:
                outgoing[child_name].add(parent_name)
                indegree[parent_name] += 1

    ready = deque(sorted(name for name, degree in indegree.items() if degree == 0))
    order: list[str] = []
    while ready:
        name = ready.popleft()
        order.append(name)
        for parent_name in sorted(outgoing[name]):
            indegree[parent_name] -= 1
            if indegree[parent_name] == 0:
                ready.append(parent_name)
    if len(order) != len(nodes):
        unresolved = sorted(nodes - set(order))
        raise HouseholdCleanupError(
            f"Cyclic target dependency requires manual review: {', '.join(unresolved)}"
        )
    return order


async def delete_cleanup_plan(
    session: AsyncSession, plan: CleanupPlan, *, backup_reference: str
) -> None:
    """Delete a pre-locked plan inside the caller's transaction and append an audit event."""
    if not backup_reference.strip():
        raise HouseholdCleanupError("A non-empty backup reference is required")
    for table_name in _deletion_order(plan.row_ids):
        table = Base.metadata.tables[table_name]
        primary_key = _single_primary_key(table)
        expected = len(plan.row_ids[table_name])
        result = await session.execute(
            delete(table).where(primary_key.in_(plan.row_ids[table_name]))
        )
        if result.rowcount is not None and result.rowcount >= 0 and result.rowcount != expected:
            raise HouseholdCleanupError(
                "Delete count mismatch for "
                f"{table_name}: expected {expected}, got {result.rowcount}"
            )

    session.add(
        PlatformAuditLog(
            actor_user_id=None,
            target_user_id=None,
            event_type="maintenance_household_cleanup",
            metadata_json={
                "family_id": str(plan.family_id),
                "child_ids": [str(child.id) for child in plan.children],
                "retained_user_ids": [str(member.id) for member in plan.members],
                "deleted_counts": plan.table_counts,
                "object_candidates": len(plan.object_keys),
                "backup_reference": backup_reference,
            },
        )
    )


async def _object_reference_count(session: AsyncSession, object_key: str) -> int:
    references = 0
    for table in Base.metadata.tables.values():
        for column_name in OBJECT_STORAGE_COLUMNS:
            column = table.c.get(column_name)
            if column is None:
                continue
            references += int(
                await session.scalar(
                    select(func.count()).select_from(table).where(column == object_key)
                )
                or 0
            )
    return references


async def cleanup_unreferenced_objects(object_keys: frozenset[str]) -> MediaCleanupResult:
    if not object_keys:
        return MediaCleanupResult(0, 0, 0, 0)
    storage = build_private_object_storage()
    removed = retained_referenced = retained_on_error = 0
    async with async_session_factory() as session:
        for object_key in object_keys:
            if await _object_reference_count(session, object_key):
                retained_referenced += 1
                continue
            try:
                await storage.remove(object_key)
                removed += 1
            except Exception:  # noqa: BLE001 - retaining an orphan is the required safe fallback
                retained_on_error += 1
        await session.rollback()
    return MediaCleanupResult(
        candidates=len(object_keys),
        removed=removed,
        retained_referenced=retained_referenced,
        retained_on_error=retained_on_error,
    )


def print_plan(plan: CleanupPlan) -> None:
    print("TARGET FAMILY")
    print(f"Family ID: {plan.family_id}")
    print(f"Family name: {plan.family_name}")
    print("\nMEMBERS")
    for member in plan.members:
        print(f"{member.display_name} | {member.email} | {member.id}")
    if not plan.members:
        print("(none)")
    print("\nCHILDREN")
    for child in plan.children:
        label = f"{child.display_name} / {child.nickname}" if child.nickname else child.display_name
        print(f"{label} | {child.id}")
    if not plan.children:
        print("(none)")
    print("\nWILL DELETE")
    for table_name, count in plan.table_counts.items():
        print(f"{table_name}: {count}")
    print(f"minio_object_candidates: {len(plan.object_keys)}")
    print("\nWILL KEEP")
    for member in plan.members:
        print(f"User {member.display_name} | {member.id}")


async def run(args: argparse.Namespace) -> int:
    family_id = args.family_id
    if args.execute:
        if args.confirm_family_id != family_id:
            raise HouseholdCleanupError(
                "--confirm-family-id must exactly match --family-id in execute mode"
            )
        if not args.backup_reference:
            raise HouseholdCleanupError("--backup-reference is required in execute mode")

    if args.dry_run:
        async with async_session_factory() as session:
            plan = await build_cleanup_plan(session, family_id)
            print_plan(plan)
            await session.rollback()
        print("\nNO DATA HAS BEEN MODIFIED")
        return 0

    async with async_session_factory() as session, session.begin():
        plan = await build_cleanup_plan(session, family_id, lock=True)
        print_plan(plan)
        await delete_cleanup_plan(session, plan, backup_reference=args.backup_reference)
    print("\nDATABASE TRANSACTION COMMITTED")
    media = await cleanup_unreferenced_objects(plan.object_keys)
    print(
        "MINIO CLEANUP "
        f"candidates={media.candidates} removed={media.removed} "
        f"retained_referenced={media.retained_referenced} "
        f"retained_on_error={media.retained_on_error}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete one explicitly confirmed test family using the complete FK graph"
    )
    parser.add_argument("--family-id", type=uuid.UUID, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-family-id", type=uuid.UUID)
    parser.add_argument("--backup-reference")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        raise SystemExit(asyncio.run(run(args)))
    except HouseholdCleanupError as error:
        raise SystemExit(f"HOUSEHOLD CLEANUP ABORTED: {error}") from error


if __name__ == "__main__":
    main()
