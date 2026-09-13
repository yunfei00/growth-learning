"""Child-private serialized reading series and ordered episode content."""

import uuid

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class StorySeries(TimestampMixin, Base):
    __tablename__ = "story_series"
    __table_args__ = (
        UniqueConstraint("child_id", "slug", name="uq_story_series_child_slug"),
        CheckConstraint("season_number >= 1", name="ck_story_series_season_number"),
        CheckConstraint("total_episodes >= 1", name="ck_story_series_total_episodes"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    season_number: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    total_episodes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_version: Mapped[str] = mapped_column(String(30), nullable=False)


class StoryEpisode(TimestampMixin, Base):
    __tablename__ = "story_episodes"
    __table_args__ = (
        UniqueConstraint("series_id", "episode_number", name="uq_story_episode_series_number"),
        UniqueConstraint("story_version_id", name="uq_story_episode_story_version"),
        CheckConstraint("episode_number >= 1", name="ck_story_episode_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_series.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_title: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    paragraphs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    focus_characters: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    story_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), index=True
    )
