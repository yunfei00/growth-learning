"""Declarative metadata shared by all future business models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class imported by Alembic for migration discovery."""
