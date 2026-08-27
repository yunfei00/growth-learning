"""System-owned canonical knowledge catalog models."""

import uuid
from datetime import datetime
from enum import StrEnum

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.identity import TimestampMixin


class KnowledgeType(StrEnum):
    CHINESE_CHARACTER = "chinese_character"
    PINYIN_INITIAL = "pinyin_initial"
    PINYIN_FINAL = "pinyin_final"
    PINYIN_TONE = "pinyin_tone"
    PINYIN_SYLLABLE = "pinyin_syllable"
    MATH_SKILL = "math_skill"
    ENGLISH_LETTER = "english_letter"
    ENGLISH_WORD = "english_word"
    ENGLISH_PHONICS = "english_phonics"
    SCIENCE_CONCEPT = "science_concept"


class Subject(StrEnum):
    CHINESE = "chinese"
    MATH = "math"
    ENGLISH = "english"
    SCIENCE = "science"


class KnowledgeStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class RelationType(StrEnum):
    RELATED = "related"
    PREREQUISITE = "prerequisite"
    CONFUSING = "confusing"
    DERIVED = "derived"


class PinyinKind(StrEnum):
    INITIAL = "initial"
    FINAL = "final"
    TONE = "tone"
    WHOLE = "whole"


class KnowledgePoint(TimestampMixin, Base):
    """Generic canonical learning item, independent from every child."""

    __tablename__ = "knowledge_points"
    __table_args__ = (
        CheckConstraint(
            "type IN ('chinese_character', 'pinyin_initial', 'pinyin_final', "
            "'pinyin_tone', 'pinyin_syllable', 'math_skill', 'english_letter', "
            "'english_word', 'english_phonics', 'science_concept')",
            name="ck_knowledge_points_type",
        ),
        CheckConstraint(
            "subject IN ('chinese', 'math', 'english', 'science')",
            name="ck_knowledge_points_subject",
        ),
        CheckConstraint(
            "(type IN ('chinese_character', 'pinyin_initial', 'pinyin_final', "
            "'pinyin_tone', 'pinyin_syllable') AND subject = 'chinese') OR "
            "(type = 'math_skill' AND subject = 'math') OR "
            "(type IN ('english_letter', 'english_word', 'english_phonics') "
            "AND subject = 'english') OR "
            "(type = 'science_concept' AND subject = 'science')",
            name="ck_knowledge_points_type_subject",
        ),
        CheckConstraint("status IN ('active', 'archived')", name="ck_knowledge_points_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(
        String(30),
        default=Subject.CHINESE,
        server_default=Subject.CHINESE,
        index=True,
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=KnowledgeStatus.ACTIVE, server_default=KnowledgeStatus.ACTIVE
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    canonical_key: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(255))

    chinese_character: Mapped["ChineseCharacter | None"] = relationship(
        back_populates="knowledge_point", uselist=False, passive_deletes=True
    )
    pinyin_item: Mapped["PinyinItem | None"] = relationship(
        back_populates="knowledge_point", uselist=False, passive_deletes=True
    )


class ChineseCharacter(TimestampMixin, Base):
    """Chinese-character attributes attached one-to-one to a knowledge point."""

    __tablename__ = "chinese_characters"
    __table_args__ = (
        CheckConstraint(
            "stroke_count IS NULL OR stroke_count > 0", name="ck_chinese_characters_strokes"
        ),
    )

    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), primary_key=True
    )
    character: Mapped[str] = mapped_column(String(8), unique=True, index=True, nullable=False)
    pinyin: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    stroke_count: Mapped[int | None] = mapped_column(Integer)
    radical: Mapped[str | None] = mapped_column(String(16))
    frequency_rank: Mapped[int | None] = mapped_column(Integer)
    difficulty_level: Mapped[int | None] = mapped_column(Integer)
    simple_meaning: Mapped[str | None] = mapped_column(Text)
    example_sentence: Mapped[str | None] = mapped_column(Text)
    parent_tip: Mapped[str | None] = mapped_column(Text)
    common_words: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)

    knowledge_point: Mapped[KnowledgePoint] = relationship(back_populates="chinese_character")


class PinyinCatalogRelease(TimestampMixin, Base):
    """Versioned provenance for the curated Pinyin foundation catalog."""

    __tablename__ = "pinyin_catalog_releases"

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


class PinyinItem(TimestampMixin, Base):
    """Domain detail for one canonical initial, final, tone, or whole syllable."""

    __tablename__ = "pinyin_items"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('initial', 'final', 'tone', 'whole')",
            name="ck_pinyin_items_kind",
        ),
        CheckConstraint("order_index >= 0", name="ck_pinyin_items_order"),
    )

    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), primary_key=True
    )
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    subcategory: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    display_text: Mapped[str] = mapped_column(String(32), nullable=False)
    pronunciation_cue: Mapped[str | None] = mapped_column(String(160))
    example_text: Mapped[str | None] = mapped_column(String(120))
    example_pinyin: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    parent_tip: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    audio_key: Mapped[str | None] = mapped_column(String(255))
    catalog_version: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    knowledge_point: Mapped[KnowledgePoint] = relationship(back_populates="pinyin_item")


class PinyinPracticeItem(TimestampMixin, Base):
    """A small curated blending exercise; it is not a required-stable knowledge point."""

    __tablename__ = "pinyin_practice_items"
    __table_args__ = (
        UniqueConstraint(
            "initial_knowledge_point_id",
            "final_knowledge_point_id",
            "display_syllable",
            name="uq_pinyin_practice_components",
        ),
        CheckConstraint("order_index >= 0", name="ck_pinyin_practice_items_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    practice_key: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    initial_knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    final_knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    display_syllable: Mapped[str] = mapped_column(String(32), nullable=False)
    underlying_final: Mapped[str] = mapped_column(String(32), nullable=False)
    display_final: Mapped[str] = mapped_column(String(32), nullable=False)
    pronunciation_cue: Mapped[str] = mapped_column(String(160), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)


class KnowledgeRelation(TimestampMixin, Base):
    """Directed generic relationship between canonical knowledge points."""

    __tablename__ = "knowledge_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "target_id", "relation_type", name="uq_knowledge_relation_edge"
        ),
        CheckConstraint("source_id <> target_id", name="ck_knowledge_relations_not_self"),
        CheckConstraint(
            "relation_type IN ('related', 'prerequisite', 'confusing', 'derived')",
            name="ck_knowledge_relations_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(24), nullable=False)
