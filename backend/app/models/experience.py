"""Child experience projections, immutable achievements, and encouragement ledger."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class AchievementDefinition(TimestampMixin, Base):
    """Versioned deterministic milestone rule, shared by every child."""

    __tablename__ = "achievement_definitions"
    __table_args__ = (
        CheckConstraint("threshold >= 1", name="ck_achievement_definitions_threshold"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(60), nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(30), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )


class ChildAchievement(TimestampMixin, Base):
    """Append-oriented, evidence-backed milestone unlock."""

    __tablename__ = "child_achievements"
    __table_args__ = (
        UniqueConstraint(
            "child_id", "achievement_definition_id", name="uq_child_achievement_definition"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    achievement_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("achievement_definitions.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    rule_version: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_source_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    evidence_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StarLedger(TimestampMixin, Base):
    """Positive-only encouragement transactions; balance is always derived."""

    __tablename__ = "star_ledger"
    __table_args__ = (
        UniqueConstraint(
            "child_id",
            "reason_type",
            "source_type",
            "source_id",
            "rule_version",
            name="uq_star_ledger_source_rule",
        ),
        CheckConstraint("amount > 0", name="ck_star_ledger_positive_amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FamilyRewardSettings(TimestampMixin, Base):
    """Family-admin encouragement policy; never a score or commerce setting."""

    __tablename__ = "family_reward_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), unique=True, index=True, nullable=False
    )
    stars_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )


class FamilyRewardGoal(TimestampMixin, Base):
    """A plain-text, parent-authored offline family encouragement goal."""

    __tablename__ = "family_reward_goals"
    __table_args__ = (CheckConstraint("required_stars > 0", name="ck_family_reward_goal_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    required_stars: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
