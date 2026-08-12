"""System-owned canonical knowledge catalog models."""

import uuid
from enum import StrEnum

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.identity import TimestampMixin


class KnowledgeType(StrEnum):
    CHINESE_CHARACTER = "chinese_character"


class KnowledgeStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class RelationType(StrEnum):
    RELATED = "related"
    PREREQUISITE = "prerequisite"
    CONFUSING = "confusing"
    DERIVED = "derived"


class KnowledgePoint(TimestampMixin, Base):
    """Generic canonical learning item, independent from every child."""

    __tablename__ = "knowledge_points"
    __table_args__ = (
        CheckConstraint("type IN ('chinese_character')", name="ck_knowledge_points_type"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_knowledge_points_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
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
    common_words: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)

    knowledge_point: Mapped[KnowledgePoint] = relationship(back_populates="chinese_character")


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
