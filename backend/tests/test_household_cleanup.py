"""The internal household cleanup follows the FK graph and never deletes adult users."""

import uuid
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli.household_cleanup import (
    HouseholdCleanupError,
    build_cleanup_plan,
    delete_cleanup_plan,
)
from app.models import (
    Child,
    ChildLearningSettings,
    DailyLearningPlan,
    DailyPlanItem,
    Family,
    FamilyMember,
    FamilyRewardSettings,
    KnowledgePoint,
    PlatformAuditLog,
    User,
)


async def seed_household(session: AsyncSession, suffix: str) -> tuple[User, Family, Child]:
    user = User(
        email=f"adult-{suffix}@example.com",
        display_name=f"Adult {suffix}",
        password_hash="not-used-in-this-test",
    )
    family = Family(name=f"Family {suffix}")
    session.add_all([user, family])
    await session.flush()
    member = FamilyMember(family_id=family.id, user_id=user.id, role="admin")
    child = Child(
        family_id=family.id,
        display_name=f"Child {suffix}",
        nickname=None,
        birth_date=date(2021, 1, 1),
        gender=None,
    )
    session.add_all([member, child, FamilyRewardSettings(family_id=family.id)])
    await session.flush()
    session.add(ChildLearningSettings(child_id=child.id))
    return user, family, child


@pytest.mark.anyio
async def test_cleanup_plan_is_fk_driven_and_dry_run_does_not_modify_data(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        target_user, target_family, target_child = await seed_household(session, "target")
        target_child.avatar_key = "private/target/avatar.jpg"
        _, other_family, other_child = await seed_household(session, "other")
        point = KnowledgePoint(
            type="chinese_character",
            status="active",
            title="Test point",
            canonical_key=f"test-{uuid.uuid4()}",
            source_type="test",
        )
        session.add(point)
        await session.flush()
        plan = DailyLearningPlan(
            child_id=target_child.id,
            plan_date=date(2026, 1, 1),
            timezone="Asia/Shanghai",
            recommended_new_count=1,
            review_count=0,
            due_count=0,
            estimated_backlog_days=0,
            recommendation_reason="test",
        )
        session.add(plan)
        await session.flush()
        session.add(
            DailyPlanItem(
                daily_plan_id=plan.id,
                knowledge_point_id=point.id,
                item_kind="new",
                position=0,
                selection_reason="test",
            )
        )
        await session.commit()
        target_user_id = target_user.id
        target_family_id = target_family.id
        target_child_id = target_child.id
        other_family_id = other_family.id
        other_child_id = other_child.id

    async with session_factory() as session:
        cleanup = await build_cleanup_plan(session, target_family_id)
        await session.rollback()

    assert cleanup.table_counts == {
        "child_learning_settings": 1,
        "children": 1,
        "daily_learning_plans": 1,
        "daily_plan_items": 1,
        "families": 1,
        "family_members": 1,
        "family_reward_settings": 1,
    }
    assert cleanup.object_keys == frozenset({"private/target/avatar.jpg"})

    async with session_factory() as session:
        assert await session.get(User, target_user_id) is not None
        assert await session.get(Family, target_family_id) is not None
        assert await session.get(Child, target_child_id) is not None
        assert await session.get(Family, other_family_id) is not None
        assert await session.get(Child, other_child_id) is not None


@pytest.mark.anyio
async def test_cleanup_executes_atomically_keeps_users_and_other_households(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        target_user, target_family, target_child = await seed_household(session, "delete")
        other_user, other_family, other_child = await seed_household(session, "keep")
        await session.commit()
        ids = {
            "target_user": target_user.id,
            "target_family": target_family.id,
            "target_child": target_child.id,
            "other_user": other_user.id,
            "other_family": other_family.id,
            "other_child": other_child.id,
        }

    async with session_factory() as session, session.begin():
        cleanup = await build_cleanup_plan(session, ids["target_family"], lock=True)
        await delete_cleanup_plan(
            session,
            cleanup,
            backup_reference="/opt/backups/growth-learning/test-backup",
        )

    async with session_factory() as session:
        assert await session.get(User, ids["target_user"]) is not None
        assert await session.get(Family, ids["target_family"]) is None
        assert await session.get(Child, ids["target_child"]) is None
        assert await session.get(User, ids["other_user"]) is not None
        assert await session.get(Family, ids["other_family"]) is not None
        assert await session.get(Child, ids["other_child"]) is not None
        audit_count = int(
            await session.scalar(
                select(func.count())
                .select_from(PlatformAuditLog)
                .where(PlatformAuditLog.event_type == "maintenance_household_cleanup")
            )
            or 0
        )
        assert audit_count == 1


@pytest.mark.anyio
async def test_cleanup_requires_backup_reference(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        _, family, _ = await seed_household(session, "backup")
        await session.commit()
        family_id = family.id

    async with session_factory() as session:
        cleanup = await build_cleanup_plan(session, family_id)
        with pytest.raises(HouseholdCleanupError, match="backup reference"):
            await delete_cleanup_plan(session, cleanup, backup_reference="")
        await session.rollback()
