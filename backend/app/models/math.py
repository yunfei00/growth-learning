"""Canonical Math Foundation content and preserved problem-level evidence."""

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.identity import TimestampMixin

if TYPE_CHECKING:
    from app.models.knowledge import KnowledgePoint


class MathDomain(StrEnum):
    CLASSIFICATION = "classification"
    QUANTITY = "quantity"
    NUMBER_SYMBOL = "number_symbol"
    COMPARISON = "comparison"
    SEQUENCE = "sequence"
    COMPOSITION = "composition"
    OPERATION = "operation"
    PATTERN = "pattern"
    GEOMETRY = "geometry"
    SPATIAL = "spatial"
    MEASUREMENT = "measurement"


class MathRepresentationType(StrEnum):
    OBJECTS = "objects"
    DOTS = "dots"
    TEN_FRAME = "ten_frame"
    NUMBER_LINE = "number_line"
    NUMERAL = "numeral"
    EQUATION = "equation"
    STORY = "story"
    SHAPE = "shape"
    PATTERN = "pattern"
    SPATIAL_SCENE = "spatial_scene"


class MathAttemptMode(StrEnum):
    PRACTICE = "practice"
    ASSESSMENT = "assessment"


class MathCatalogRelease(TimestampMixin, Base):
    """Versioned provenance for Growth Learning's project-curated math path."""

    __tablename__ = "math_catalog_releases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    catalog_version: Mapped[str] = mapped_column(
        String(80), unique=True, index=True, nullable=False
    )
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    template_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)


class MathSkill(TimestampMixin, Base):
    """One durable mathematical capability attached to a generic knowledge point."""

    __tablename__ = "math_skills"
    __table_args__ = (
        CheckConstraint(
            "domain IN ('classification', 'quantity', 'number_symbol', 'comparison', "
            "'sequence', 'composition', 'operation', 'pattern', 'geometry', 'spatial', "
            "'measurement')",
            name="ck_math_skills_domain",
        ),
        CheckConstraint("difficulty_level >= 1", name="ck_math_skills_difficulty"),
        CheckConstraint("order_index >= 0", name="ck_math_skills_order"),
        CheckConstraint(
            "recommended_age_min IS NULL OR recommended_age_max IS NULL OR "
            "recommended_age_min <= recommended_age_max",
            name="ck_math_skills_age_range",
        ),
    )

    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), primary_key=True
    )
    domain: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    skill_code: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    difficulty_level: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_age_min: Mapped[int | None] = mapped_column(Integer)
    recommended_age_max: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    child_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    parent_tip: Mapped[str] = mapped_column(Text, nullable=False)
    representation_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    generator_key: Mapped[str | None] = mapped_column(String(100), index=True)
    settings_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(80), index=True, nullable=False)

    knowledge_point: Mapped["KnowledgePoint"] = relationship(back_populates="math_skill")


class MathProblemTemplate(TimestampMixin, Base):
    """A deterministic generator configuration; it is not a knowledge point."""

    __tablename__ = "math_problem_templates"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_point_id", "order_index", name="uq_math_problem_template_order"
        ),
        CheckConstraint("difficulty >= 1", name="ck_math_problem_templates_difficulty"),
        CheckConstraint("order_index >= 0", name="ck_math_problem_templates_order"),
        CheckConstraint(
            "status IN ('active', 'archived')", name="ck_math_problem_templates_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    template_key: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    representation_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    generator_version: Mapped[str] = mapped_column(String(60), nullable=False)
    config_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)


class MathExerciseAttempt(TimestampMixin, Base):
    """Problem-level raw evidence preserving first answer, retries, and snapshot."""

    __tablename__ = "math_exercise_attempts"
    __table_args__ = (
        CheckConstraint("mode IN ('practice', 'assessment')", name="ck_math_attempts_mode"),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('correct', 'hinted_correct', 'uncertain', 'incorrect')",
            name="ck_math_attempts_outcome",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_math_attempts_attempt_count"),
        CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_math_attempts_response_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("math_problem_templates.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    template_key: Mapped[str] = mapped_column(String(160), nullable=False)
    generator_version: Mapped[str] = mapped_column(String(60), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    problem_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    expected_answer: Mapped[object] = mapped_column(JSON, nullable=False)
    submitted_answer: Mapped[object | None] = mapped_column(JSON)
    first_answer: Mapped[object | None] = mapped_column(JSON)
    outcome: Mapped[str | None] = mapped_column(String(24))
    hint_used: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    evidence_dimension: Mapped[str] = mapped_column(
        String(40), default="understanding", server_default="understanding", nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    evaluator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )


class MathDailyPlan(TimestampMixin, Base):
    """Small persisted daily workload independent from literacy and Pinyin plans."""

    __tablename__ = "math_daily_plans"
    __table_args__ = (
        UniqueConstraint("child_id", "plan_date", name="uq_math_daily_plan_child_date"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_math_daily_plans_status",
        ),
        CheckConstraint(
            "new_count >= 0 AND review_count >= 0 AND completed_count >= 0",
            name="ck_math_daily_plans_counts",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Shanghai", server_default="Asia/Shanghai", nullable=False
    )
    new_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    review_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    completed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    algorithm_version: Mapped[str] = mapped_column(
        String(30), default="math-plan-v1", server_default="math-plan-v1", nullable=False
    )


class MathDailyPlanItem(TimestampMixin, Base):
    __tablename__ = "math_daily_plan_items"
    __table_args__ = (
        UniqueConstraint(
            "math_daily_plan_id", "knowledge_point_id", name="uq_math_daily_plan_item_point"
        ),
        CheckConstraint("item_kind IN ('new', 'review')", name="ck_math_daily_plan_items_kind"),
        CheckConstraint(
            "status IN ('pending', 'completed')", name="ck_math_daily_plan_items_status"
        ),
        CheckConstraint("position >= 0", name="ck_math_daily_plan_items_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    math_daily_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("math_daily_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    item_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    problem_count: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
