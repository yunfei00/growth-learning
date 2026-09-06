"""Private imported picture-book metadata layered onto immutable story versions."""

import uuid

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class PictureBookImport(TimestampMixin, Base):
    """One auditable external picture book imported into one child's story shelf."""

    __tablename__ = "picture_book_imports"
    __table_args__ = (
        UniqueConstraint(
            "child_id", "source_provider", "source_book_id", name="uq_picture_book_child_source"
        ),
        UniqueConstraint("story_version_id", name="uq_picture_book_story_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    story_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    imported_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_book_id: Mapped[str] = mapped_column(String(80), nullable=False)
    source_h5p_id: Mapped[str | None] = mapped_column(String(80))
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    license_name: Mapped[str] = mapped_column(String(80), nullable=False)
    reading_level: Mapped[str] = mapped_column(String(40), nullable=False)
    attribution: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    pages: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list, nullable=False)
    cover_object_key: Mapped[str | None] = mapped_column(String(500))
