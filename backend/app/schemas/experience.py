"""Child-friendly projections over canonical evidence and family encouragement."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TodayTaskResponse(BaseModel):
    subject: Literal["chinese", "math", "english", "science"]
    kind: Literal["new", "review", "pinyin", "math", "reading", "science", "teacher"]
    title: str
    description: str
    status: Literal["pending", "in_progress", "completed", "needs_story", "optional"]
    count: int
    cta_label: str
    href: str
    source_type: str
    source_id: uuid.UUID | None
    urgent: bool = False


class ChildTodayResponse(BaseModel):
    child_id: uuid.UUID
    plan_date: date
    tasks: list[TodayTaskResponse]
    continue_task: TodayTaskResponse | None
    completed_count: int
    total_count: int
    star_balance: int
    newly_unlocked_achievements: int


class GrowthTreeUnitResponse(BaseModel):
    id: uuid.UUID
    title: str
    total: int
    course_completed_activities: int
    course_activity_count: int
    touched: int
    growing: int
    familiar: int


class GrowthTreeCourseResponse(BaseModel):
    id: uuid.UUID
    title: str
    source_type: str
    course_progress_percent: float
    total: int
    touched: int
    growing: int
    familiar: int
    units: list[GrowthTreeUnitResponse]


class GrowthTreeDomainResponse(BaseModel):
    completed: int
    independent: int | None = None
    questions: int | None = None


class GrowthTreeResponse(BaseModel):
    child_id: uuid.UUID
    projection_version: str
    mastery_mapping: dict[str, str]
    chinese: list[GrowthTreeCourseResponse]
    reading: GrowthTreeDomainResponse
    science: GrowthTreeDomainResponse


class AchievementResponse(BaseModel):
    id: uuid.UUID
    key: str
    title: str
    description: str
    icon: str
    rule_version: str
    evidence_source_type: str
    evidence_source_id: uuid.UUID | None
    evidence_snapshot: dict[str, object]
    unlocked_at: datetime


class StarLedgerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: int
    reason_type: str
    source_type: str
    source_id: uuid.UUID
    rule_version: str
    occurred_at: datetime


class RewardGoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    required_stars: int
    is_active: bool


class AchievementSummaryResponse(BaseModel):
    child_id: uuid.UUID
    stars_enabled: bool
    star_balance: int
    achievements: list[AchievementResponse]
    recent_ledger: list[StarLedgerResponse]
    next_reward_goal: RewardGoalResponse | None


class AchievementRebuildResponse(BaseModel):
    child_id: uuid.UUID
    definitions: int
    created: int
    existing: int
    rewards_created: int
    star_balance: int


class RewardSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stars_enabled: bool


class RewardSettingsResponse(BaseModel):
    family_id: uuid.UUID
    stars_enabled: bool
    goals: list[RewardGoalResponse]


class RewardGoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    required_stars: int = Field(ge=1, le=10000)


class RewardGoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    required_stars: int | None = Field(default=None, ge=1, le=10000)
    is_active: bool | None = None
