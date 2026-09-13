"""Contracts for serialized reading progress and episode navigation."""

import uuid

from pydantic import BaseModel


class ReadingSeriesEpisodeResponse(BaseModel):
    episode_number: int
    chapter_title: str
    title: str
    status: str
    story_version_id: uuid.UUID | None
    paragraphs: list[str]
    focus_characters: list[str]


class ReadingSeriesEpisodeOpenResponse(BaseModel):
    episode_number: int
    story_version_id: uuid.UUID


class ReadingSeriesProgressResponse(BaseModel):
    series_id: uuid.UUID
    slug: str
    title: str
    season_number: int
    total_episodes: int
    completed_episodes: int
    progress_percent: float
    current_episode_number: int | None
    current_episode_title: str | None
    current_chapter_title: str | None
    current_story_version_id: uuid.UUID | None
    episodes: list[ReadingSeriesEpisodeResponse]
