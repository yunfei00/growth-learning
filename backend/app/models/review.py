"""Derived adaptive-review, daily-plan, and bounded literacy projections."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class DailyPlanStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class DailyPlanItemKind(StrEnum):
    NEW = "new"
    REVIEW = "review"


class PlanItemStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class AssessmentSource(StrEnum):
    QUICK_TEST = "quick_test"
    DAILY_REVIEW = "daily_review"
    WEEKLY_CHECK = "weekly_check"
    MONTHLY_ASSESSMENT = "monthly_assessment"


class ChildLearningSettings(TimestampMixin, Base):
    """Family-admin configuration for one child's deterministic workload."""

    __tablename__ = "child_learning_settings"
    __table_args__ = (
        UniqueConstraint("child_id", name="uq_child_learning_settings_child"),
        CheckConstraint(
            "max_new_characters_per_day >= 0 AND max_new_characters_per_day <= 20",
            name="ck_child_learning_settings_max_new",
        ),
        CheckConstraint(
            "daily_review_capacity >= 1 AND daily_review_capacity <= 100",
            name="ck_child_learning_settings_review_capacity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), unique=True, index=True, nullable=False
    )
    max_new_characters_per_day: Mapped[int] = mapped_column(
        Integer, default=5, server_default="5", nullable=False
    )
    daily_review_capacity: Mapped[int] = mapped_column(
        Integer, default=15, server_default="15", nullable=False
    )
    weekly_assessment_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    monthly_assessment_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Shanghai", server_default="Asia/Shanghai", nullable=False
    )


class ChildReviewSchedule(TimestampMixin, Base):
    """Rebuildable next-review projection for a child/knowledge-point pair."""

    __tablename__ = "child_review_schedules"
    __table_args__ = (
        UniqueConstraint(
            "child_id", "knowledge_point_id", name="uq_child_review_schedule_child_point"
        ),
        CheckConstraint("interval_days >= 1", name="ck_child_review_schedules_interval_days"),
        CheckConstraint("interval_stage >= 0", name="ck_child_review_schedules_interval_stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    last_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_review_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_stage: Mapped[int] = mapped_column(Integer, nullable=False)
    last_outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduling_reason: Mapped[str] = mapped_column(String(80), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(
        String(20), default="review-v1", server_default="review-v1", nullable=False
    )


class DailyLearningPlan(TimestampMixin, Base):
    """One resumable, local-calendar learning plan per child and day."""

    __tablename__ = "daily_learning_plans"
    __table_args__ = (
        UniqueConstraint("child_id", "plan_date", name="uq_daily_learning_plan_child_date"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_daily_learning_plans_status",
        ),
        CheckConstraint(
            "recommended_new_count >= 0 AND review_count >= 0 AND due_count >= 0",
            name="ck_daily_learning_plans_counts",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    recommended_new_count: Mapped[int] = mapped_column(Integer, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False)
    due_count: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_backlog_days: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    new_completed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    review_completed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(20), default=DailyPlanStatus.PENDING, server_default="pending", nullable=False
    )
    algorithm_version: Mapped[str] = mapped_column(
        String(20), default="plan-v1", server_default="plan-v1", nullable=False
    )


class DailyPlanItem(TimestampMixin, Base):
    """Persisted deterministic selections that make a daily plan resumable."""

    __tablename__ = "daily_plan_items"
    __table_args__ = (
        UniqueConstraint(
            "daily_plan_id", "knowledge_point_id", "item_kind", name="uq_daily_plan_item_point_kind"
        ),
        CheckConstraint("item_kind IN ('new', 'review')", name="ck_daily_plan_items_kind"),
        CheckConstraint("status IN ('pending', 'completed')", name="ck_daily_plan_items_status"),
        CheckConstraint("position >= 0", name="ck_daily_plan_items_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    daily_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("daily_learning_plans.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    item_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=PlanItemStatus.PENDING, server_default="pending", nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    selection_reason: Mapped[str] = mapped_column(String(80), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssessmentSessionPlan(TimestampMixin, Base):
    """Reproducible selection frame attached to an existing assessment session."""

    __tablename__ = "assessment_session_plans"
    __table_args__ = (
        UniqueConstraint("assessment_session_id", name="uq_assessment_session_plan_session"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
        nullable=False,
    )
    daily_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("daily_learning_plans.id", ondelete="RESTRICT"), index=True
    )
    sampling_method: Mapped[str] = mapped_column(String(60), nullable=False)
    sampling_version: Mapped[str] = mapped_column(String(20), nullable=False)
    eligible_catalog_size: Mapped[int] = mapped_column(Integer, nullable=False)


class AssessmentSessionTarget(TimestampMixin, Base):
    """Persisted prompt selection; outcomes remain solely in AssessmentItem."""

    __tablename__ = "assessment_session_targets"
    __table_args__ = (
        UniqueConstraint(
            "assessment_session_id",
            "knowledge_point_id",
            name="uq_assessment_session_target_point",
        ),
        CheckConstraint("position >= 0", name="ck_assessment_session_targets_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    sampling_class: Mapped[str] = mapped_column(String(40), nullable=False)


class LiteracyEstimate(TimestampMixin, Base):
    """Catalog-bounded estimate derived from a completed monthly assessment."""

    __tablename__ = "literacy_estimates"
    __table_args__ = (
        UniqueConstraint("assessment_session_id", name="uq_literacy_estimate_session"),
        CheckConstraint(
            "catalog_size >= 0 AND sample_size >= 0 AND known_count >= 0 AND unknown_count >= 0",
            name="ck_literacy_estimates_counts",
        ),
        CheckConstraint(
            "estimate IS NULL OR (estimate >= 0 AND estimate <= catalog_size)",
            name="ck_literacy_estimates_value",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    assessment_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
        nullable=False,
    )
    catalog_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    known_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unknown_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sampling_method: Mapped[str] = mapped_column(String(60), nullable=False)
    sampling_version: Mapped[str] = mapped_column(String(20), nullable=False)
    estimate: Mapped[float | None] = mapped_column(Float)
    lower_bound: Mapped[float | None] = mapped_column(Float)
    upper_bound: Mapped[float | None] = mapped_column(Float)
    is_sufficient: Mapped[bool] = mapped_column(Boolean, nullable=False)
    estimation_version: Mapped[str] = mapped_column(
        String(20), default="literacy-v1", server_default="literacy-v1", nullable=False
    )
