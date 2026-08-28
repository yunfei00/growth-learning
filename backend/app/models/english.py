"""Canonical English Foundation content and preserved exercise evidence."""

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


class EnglishKind(StrEnum):
    LETTER = "letter"
    WORD = "word"
    PHONICS = "phonics"
    PHRASE = "phrase"


class EnglishVisualType(StrEnum):
    STATIC_IMAGE = "static_image"
    ICON = "icon"
    COLOR_SWATCH = "color_swatch"
    SHAPE = "shape"
    EMOJI_FALLBACK = "emoji_fallback"


class EnglishAttemptMode(StrEnum):
    PRACTICE = "practice"
    ASSESSMENT = "assessment"


class EnglishCatalogRelease(TimestampMixin, Base):
    __tablename__ = "english_catalog_releases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    catalog_version: Mapped[str] = mapped_column(
        String(80), unique=True, index=True, nullable=False
    )
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    practice_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)


class EnglishItem(TimestampMixin, Base):
    """One durable letter, word, phonics concept, or useful phrase."""

    __tablename__ = "english_items"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('letter', 'word', 'phonics', 'phrase')",
            name="ck_english_items_kind",
        ),
        CheckConstraint(
            "visual_type IN ('static_image', 'icon', 'color_swatch', 'shape', 'emoji_fallback')",
            name="ck_english_items_visual_type",
        ),
        CheckConstraint("order_index >= 0", name="ck_english_items_order"),
    )

    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    text: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    meaning_zh: Mapped[str] = mapped_column(String(240), nullable=False)
    child_hint_zh: Mapped[str] = mapped_column(Text, nullable=False)
    parent_tip: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    example_text: Mapped[str | None] = mapped_column(String(240))
    example_meaning_zh: Mapped[str | None] = mapped_column(String(240))
    image_key: Mapped[str | None] = mapped_column(String(255))
    visual_key: Mapped[str | None] = mapped_column(String(160))
    visual_type: Mapped[str] = mapped_column(
        String(30), default="emoji_fallback", server_default="emoji_fallback", nullable=False
    )
    audio_key: Mapped[str | None] = mapped_column(String(255))
    audio_accent: Mapped[str] = mapped_column(
        String(20), default="en-US", server_default="en-US", nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    knowledge_point: Mapped["KnowledgePoint"] = relationship(back_populates="english_item")


class EnglishPracticeItem(TimestampMixin, Base):
    """A versioned deterministic exercise template, never a KnowledgePoint."""

    __tablename__ = "english_practice_items"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_point_id", "order_index", name="uq_english_practice_item_order"
        ),
        CheckConstraint(
            "practice_kind IN ('listen_choose_visual', 'visual_choose_audio', "
            "'letter_match', 'case_match', 'phonics_choose', 'blending', "
            "'phrase_listening')",
            name="ck_english_practice_items_kind",
        ),
        CheckConstraint(
            "status IN ('active', 'archived')", name="ck_english_practice_items_status"
        ),
        CheckConstraint("order_index >= 0", name="ck_english_practice_items_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    template_key: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    practice_kind: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    generator_version: Mapped[str] = mapped_column(String(60), nullable=False)
    config_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)


class EnglishExerciseAttempt(TimestampMixin, Base):
    """Problem-level raw evidence preserving the first response and all retries."""

    __tablename__ = "english_exercise_attempts"
    __table_args__ = (
        CheckConstraint("mode IN ('practice', 'assessment')", name="ck_english_attempts_mode"),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('correct', 'hinted_correct', 'uncertain', 'incorrect')",
            name="ck_english_attempts_outcome",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_english_attempts_count"),
        CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_english_attempts_response_time",
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
    practice_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("english_practice_items.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    template_key: Mapped[str] = mapped_column(String(180), nullable=False)
    practice_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    generator_version: Mapped[str] = mapped_column(String(60), nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer)
    prompt_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    options_snapshot: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    expected_answer: Mapped[object] = mapped_column(JSON, nullable=False)
    submitted_answer: Mapped[object | None] = mapped_column(JSON)
    first_answer: Mapped[object | None] = mapped_column(JSON)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    hint_used: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    audio_replay_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    outcome: Mapped[str | None] = mapped_column(String(24))
    evidence_dimension: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    evaluator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )


class EnglishDailyPlan(TimestampMixin, Base):
    __tablename__ = "english_daily_plans"
    __table_args__ = (
        UniqueConstraint("child_id", "plan_date", name="uq_english_daily_plan_child_date"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_english_daily_plans_status",
        ),
        CheckConstraint(
            "new_count >= 0 AND review_count >= 0 AND completed_count >= 0",
            name="ck_english_daily_plans_counts",
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
        String(30), default="english-plan-v1", server_default="english-plan-v1", nullable=False
    )


class EnglishDailyPlanItem(TimestampMixin, Base):
    __tablename__ = "english_daily_plan_items"
    __table_args__ = (
        UniqueConstraint(
            "english_daily_plan_id",
            "knowledge_point_id",
            name="uq_english_daily_plan_item_point",
        ),
        CheckConstraint("item_kind IN ('new', 'review')", name="ck_english_daily_plan_items_kind"),
        CheckConstraint(
            "status IN ('pending', 'completed')", name="ck_english_daily_plan_items_status"
        ),
        CheckConstraint("position >= 0", name="ck_english_daily_plan_items_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    english_daily_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("english_daily_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    item_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    exercise_count: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
