"""API contracts for reusable course paths and catalog provenance."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CourseKnowledgePointInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    knowledge_point_id: uuid.UUID
    role: str = Field(default="primary", pattern="^(primary|review|optional|prerequisite)$")
    reference_code: str | None = Field(default=None, max_length=160)
    curriculum_metadata: dict[str, object] = Field(default_factory=dict)


class CourseActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    activity_type: str = Field(
        default="character_learning",
        pattern=(
            "^(knowledge_learning|guided_practice|independent_practice|knowledge_review|"
            "knowledge_check|listening|speaking|character_learning|character_review|"
            "recognition_check|reading|science_reference|offline_instruction)$"
        ),
    )
    instructions: str | None = Field(default=None, max_length=2000)
    knowledge_points: list[CourseKnowledgePointInput] = Field(default_factory=list, max_length=200)


class CourseUnitInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    activities: list[CourseActivityInput] = Field(min_length=1, max_length=100)


class CourseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(default="chinese", pattern="^(chinese|math|english|science)$")
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    source_type: str = Field(pattern="^(system|family|teacher|textbook_reference)$")
    recommended_age_min: int | None = Field(default=None, ge=0, le=18)
    recommended_age_max: int | None = Field(default=None, ge=0, le=18)
    reference_metadata: dict[str, str] = Field(default_factory=dict)
    education_stage: str = Field(
        default="foundation", pattern="^(foundation|primary|junior_middle)$"
    )
    grade_level: int | None = Field(default=None, ge=1, le=9)
    semester: str = Field(default="full_year", pattern="^(full_year|semester_1|semester_2)$")
    units: list[CourseUnitInput] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def age_order(self) -> "CourseCreate":
        if (
            self.recommended_age_min is not None
            and self.recommended_age_max is not None
            and self.recommended_age_min > self.recommended_age_max
        ):
            raise ValueError("recommended_age_min cannot exceed recommended_age_max")
        if self.education_stage == "foundation" and self.grade_level is not None:
            raise ValueError("foundation courses cannot have a grade level")
        if self.education_stage == "primary" and self.grade_level not in range(1, 7):
            raise ValueError("primary courses require grade level 1 through 6")
        if self.education_stage == "junior_middle" and self.grade_level not in range(7, 10):
            raise ValueError("junior_middle courses require grade level 7 through 9")
        return self


class CoursePointResponse(BaseModel):
    mapping_id: uuid.UUID
    knowledge_point_id: uuid.UUID
    title: str
    subject: str
    knowledge_type: str
    character: str | None
    pinyin: str | None
    role: str
    order_index: int
    mastery_level: str | None
    mastery_policy_key: str | None
    projection_status: str
    reference_code: str | None = None
    curriculum_metadata: dict = Field(default_factory=dict)


class CourseActivityResponse(BaseModel):
    id: uuid.UUID
    title: str
    activity_type: str
    instructions: str | None
    order_index: int
    status: str
    lesson_id: uuid.UUID | None = None
    progress_status: str
    points: list[CoursePointResponse]


class CourseLessonResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    order_index: int
    estimated_minutes: int | None
    status: str
    metadata_json: dict
    activity_count: int
    completed_activities: int
    activities: list[CourseActivityResponse]


class CourseUnitResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    order_index: int
    status: str
    activity_count: int
    completed_activities: int
    introduced_count: int
    stable_count: int
    unlearned_count: int
    projection_unavailable_count: int
    lessons: list[CourseLessonResponse] = Field(default_factory=list)
    activities: list[CourseActivityResponse]


class CourseResponse(BaseModel):
    id: uuid.UUID
    subject: str
    title: str
    description: str | None
    source_type: str
    status: str
    version: int
    education_stage: str
    education_stage_label: str
    grade_level: int | None
    grade_level_label: str
    semester: str
    semester_label: str
    curriculum_key: str | None
    curriculum_version: str | None
    curriculum_release_id: uuid.UUID | None
    curriculum_release_status: str | None
    recommended_age_min: int | None
    recommended_age_max: int | None
    reference_metadata: dict
    enrollment_id: uuid.UUID | None
    enrollment_status: str | None
    path_order: int | None
    activity_count: int
    completed_activities: int
    progress_percent: float
    introduced_count: int
    stable_count: int
    unlearned_count: int
    projection_unavailable_count: int
    units: list[CourseUnitResponse]
    created_at: datetime
    updated_at: datetime


class EnrollmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: uuid.UUID
    path_order: int = Field(default=0, ge=0, le=1000)
    status: str = Field(default="active", pattern="^(planned|active)$")


class CourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, pattern="^(draft|enabled|archived)$")


class EnrollmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str | None = Field(default=None, pattern="^(planned|active|paused|completed|archived)$")
    path_order: int | None = Field(default=None, ge=0, le=1000)


class EnrollmentResponse(BaseModel):
    id: uuid.UUID
    child_id: uuid.UUID
    course_id: uuid.UUID
    course_title: str
    course_version: int
    curriculum_release_id: uuid.UUID | None
    curriculum_version: str | None
    status: str
    path_order: int
    started_at: datetime | None
    completed_at: datetime | None
    progress_percent: float


class PathCopyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_child_id: uuid.UUID


class PathCopyResponse(BaseModel):
    copied_enrollments: int
    mastery_copied: bool = False
    history_copied: bool = False


class CourseActivityCompletionResponse(BaseModel):
    activity_id: uuid.UUID
    progress_status: str
    learning_session_id: uuid.UUID
    learning_records_created: int
    mastery_directly_modified: bool = False


class CatalogReleaseResponse(BaseModel):
    catalog_version: str
    item_count: int
    source_type: str
    source_name: str
    source_reference: str | None
    license: str | None
    imported_at: datetime
    is_current: bool
    metadata: dict


class CatalogImportResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    preserved: int
    catalog_version: str
    catalog_size: int
    course_created: bool
    errors: list[str]
