"""API contracts for Math Foundation V1."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MathStateValue = Literal["unlearned", "introduced", "practicing", "proficient", "stable"]
MathModeValue = Literal["practice", "assessment"]
MathDimensionValue = Literal["understanding", "independent", "transfer"]


class MathTemplateSummary(BaseModel):
    id: uuid.UUID
    template_key: str
    representation_type: str
    difficulty: int
    generator_version: str
    status: Literal["active", "archived"]


class MathSkillSummary(BaseModel):
    knowledge_point_id: uuid.UUID
    canonical_key: str
    domain: str
    skill_code: str
    title: str
    difficulty_level: int
    order_index: int
    status: Literal["active", "archived"]
    representation_types: list[str]
    template_count: int
    state_code: MathStateValue = "unlearned"
    learned: bool = False


class MathSkillPage(BaseModel):
    items: list[MathSkillSummary]
    page: int
    page_size: int
    total: int
    pages: int


class MathNavigationItem(BaseModel):
    knowledge_point_id: uuid.UUID
    title: str


class MathSkillDetail(MathSkillSummary):
    child_instruction: str
    parent_tip: str
    recommended_age_min: int | None
    recommended_age_max: int | None
    generator_key: str | None
    settings: dict[str, object]
    catalog_version: str
    templates: list[MathTemplateSummary]
    prerequisites: list[MathNavigationItem]
    position: int
    total: int
    previous: MathNavigationItem | None
    next: MathNavigationItem | None
    policy_key: str
    dimensions: dict[str, object]
    mastery_explanation: list[str]
    common_difficulties: list[str]
    last_learning_at: datetime | None
    last_assessed_at: datetime | None
    next_review_at: datetime | None


class MathOverviewGroup(BaseModel):
    domain: str
    label: str
    total: int
    learned: int
    proficient: int
    stable: int
    state_code: MathStateValue


class MathOverviewResponse(BaseModel):
    child_id: uuid.UUID
    catalog_version: str
    total: int
    learned: int
    stable: int
    groups: list[MathOverviewGroup]


class MathTodayItem(MathSkillSummary):
    item_kind: Literal["new", "review"]
    problem_count: int
    completed: bool


class MathTodayResponse(BaseModel):
    plan_id: uuid.UUID
    child_id: uuid.UUID
    plan_date: date
    items: list[MathTodayItem]
    completed_count: int
    target_count: int
    status: Literal["pending", "in_progress", "completed"]
    estimated_minutes: int = 5


class MathProblemResponse(BaseModel):
    attempt_id: uuid.UUID
    template_key: str
    generator_version: str
    seed: int
    representation_type: str
    render_payload: dict[str, object]
    answered: bool = False


class MathSessionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_point_id: uuid.UUID
    mode: MathModeValue = "practice"
    problem_count: int = Field(default=3, ge=1, le=5)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_000)
    dimension: MathDimensionValue = "understanding"


class MathSessionResponse(BaseModel):
    session_id: uuid.UUID
    child_id: uuid.UUID
    knowledge_point_id: uuid.UUID
    skill_title: str
    mode: MathModeValue
    dimension: MathDimensionValue
    problems: list[MathProblemResponse]
    completed_count: int
    total_count: int
    completed: bool


class MathAttemptAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submitted_answer: Any
    hint_used: bool = False
    response_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class MathAttemptAnswerResponse(BaseModel):
    attempt_id: uuid.UUID
    outcome: Literal["correct", "hinted_correct", "uncertain", "incorrect"]
    first_answer_correct: bool
    attempt_count: int
    hint_used: bool
    feedback: str
    correct_answer: Any
    session_completed: bool
    mastery_state: MathStateValue | None = None


class MathOfflineObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["correct", "hinted_correct", "uncertain"]


class MathOfflineObservationResponse(BaseModel):
    assessment_item_id: uuid.UUID
    outcome: Literal["correct", "hinted_correct", "uncertain"]
    mastery_state: MathStateValue


class MathHistorySkill(BaseModel):
    knowledge_point_id: uuid.UUID
    title: str
    domain: str
    problem_count: int
    correct: int
    hinted_correct: int
    uncertain: int
    incorrect: int
    representations: list[str]


class MathHistorySession(BaseModel):
    session_id: uuid.UUID
    mode: Literal["practice", "assessment", "offline"]
    actor_display_name: str
    occurred_at: datetime
    skills: list[MathHistorySkill]


class MathHistoryResponse(BaseModel):
    child_id: uuid.UUID
    items: list[MathHistorySession]


class MathSkillUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "archived"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    child_instruction: str | None = Field(default=None, min_length=1, max_length=2000)
    parent_tip: str | None = Field(default=None, min_length=1, max_length=2000)
    recommended_age_min: int | None = Field(default=None, ge=0, le=18)
    recommended_age_max: int | None = Field(default=None, ge=0, le=18)


class MathImportResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    relations_created: int
    templates_created: int
    catalog_version: str
    catalog_size: int
    template_count: int
    course_created: bool
    errors: list[str]
