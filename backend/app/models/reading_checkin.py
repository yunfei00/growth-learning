"""Append-only reading assistance events used by daily reading check-ins."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class ReadingHelpEvent(TimestampMixin, Base):
    """One child-initiated request for help while reading a story.

    These rows are behavioral reading evidence only. They must never be treated
    as a correct/incorrect character assessment or directly mutate mastery.
    """

    __tablename__ = "reading_help_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reading_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reading_sessions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    story_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True
    )
    character: Mapped[str] = mapped_column(String(8), nullable=False)
    pinyin: Mapped[str | None] = mapped_column(String(40))
    help_kind: Mapped[str] = mapped_column(
        String(30), default="character_tap", server_default="character_tap", nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
