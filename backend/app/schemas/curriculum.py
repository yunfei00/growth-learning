"""Curriculum release, builder, validation, and portable JSON contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.course import CourseResponse


def _validate_stage_grade(stage: str, grade: int | None) -> None:
    if stage == "foundation" and grade is not None:
        raise ValueError("foundation releases cannot have a grade level")
    if stage == "primary" and grade not in range(1, 7):
        raise ValueError("primary releases require grade level 1 through 6")
    if stage == "junior_middle" and grade not in range(7, 10):
        raise ValueError("junior_middle releases require grade level 7 through 9")


class CurriculumReleaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curriculum_key: str = Field(min_length=3, max_length=180, pattern=r"^[a-z0-9][a-z0-9:_-]+$")
    release_version: str = Field(min_length=1, max_length=80)
    education_stage: str = Field(pattern="^(foundation|primary|junior_middle)$")
    grade_level: int | None = Field(default=None, ge=1, le=9)
    semester: str = Field(pattern="^(full_year|semester_1|semester_2)$")
    subject: str = Field(pattern="^(chinese|math|english|science)$")
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    source_type: str = Field(
        default="project_curated",
        pattern=(
            "^(project_curated|curriculum_standard_reference|textbook_reference|teacher_curated)$"
        ),
    )
    source_name: str = Field(default="Growth Learning", min_length=1, max_length=160)
    source_reference: str | None = Field(default=None, max_length=500)
    license: str | None = Field(default="project_owned", max_length=120)
    copyright_notice: str | None = Field(default=None, max_length=2000)
    change_summary: str | None = Field(default=None, max_length=4000)
    metadata_json: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def stage_matches_grade(self) -> "CurriculumReleaseCreate":
        _validate_stage_grade(self.education_stage, self.grade_level)
        return self


class CurriculumReleaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    source_name: str | None = Field(default=None, min_length=1, max_length=160)
    source_reference: str | None = Field(default=None, max_length=500)
    license: str | None = Field(default=None, max_length=120)
    copyright_notice: str | None = Field(default=None, max_length=2000)
    change_summary: str | None = Field(default=None, max_length=4000)
    metadata_json: dict[str, object] | None = None


class CurriculumUnitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class CurriculumLessonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    estimated_minutes: int | None = Field(default=None, ge=1, le=600)
    metadata_json: dict[str, object] = Field(default_factory=dict)


class CurriculumActivityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    activity_type: str = Field(
        default="knowledge_learning",
        pattern=(
            "^(knowledge_learning|guided_practice|independent_practice|knowledge_review|"
            "knowledge_check|listening|speaking|character_learning|character_review|"
            "recognition_check|reading|science_reference|offline_instruction)$"
        ),
    )
    instructions: str | None = Field(default=None, max_length=4000)
    content_metadata: dict[str, object] = Field(default_factory=dict)


class CurriculumMappingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    knowledge_point_id: uuid.UUID
    role: str = Field(default="primary", pattern="^(primary|review|optional|prerequisite)$")
    reference_code: str | None = Field(default=None, max_length=160)
    metadata_json: dict[str, object] = Field(default_factory=dict)


class CurriculumNodeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    instructions: str | None = Field(default=None, max_length=4000)
    estimated_minutes: int | None = Field(default=None, ge=1, le=600)
    status: str | None = Field(default=None, pattern="^(draft|enabled|archived)$")
    metadata_json: dict[str, object] | None = None


class CurriculumMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    direction: str = Field(pattern="^(up|down)$")


class CurriculumTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_warnings: bool = False


class CurriculumNewVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    release_version: str = Field(min_length=1, max_length=80)
    change_summary: str = Field(min_length=1, max_length=4000)


class CurriculumValidationIssue(BaseModel):
    severity: str
    code: str
    message: str
    path: str


class CurriculumValidationReport(BaseModel):
    valid: bool
    issues: list[CurriculumValidationIssue]
    error_count: int
    warning_count: int
    checks: dict[str, bool]
    statistics: dict[str, int]


class CurriculumReleaseResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    curriculum_key: str
    release_version: str
    education_stage: str
    education_stage_label: str
    grade_level: int | None
    grade_level_label: str
    semester: str
    semester_label: str
    subject: str
    title: str
    description: str | None
    status: str
    source_type: str
    source_name: str
    source_reference: str | None
    license: str | None
    copyright_notice: str | None
    created_by_user_id: uuid.UUID
    reviewed_by_user_id: uuid.UUID | None
    published_by_user_id: uuid.UUID | None
    created_at: datetime
    reviewed_at: datetime | None
    published_at: datetime | None
    archived_at: datetime | None
    change_summary: str | None
    validation_snapshot: dict
    metadata_json: dict
    unit_count: int
    lesson_count: int
    activity_count: int
    knowledge_point_count: int
    course: CourseResponse | None = None


class CurriculumPreviewResponse(BaseModel):
    preview_mode: bool = True
    writes_learning_data: bool = False
    release: CurriculumReleaseResponse


class CurriculumImportReport(BaseModel):
    dry_run: bool
    will_create: list[str]
    will_update: list[str]
    created: list[str]
    updated: list[str]
    errors: list[str]
    warnings: list[str]
    release_id: uuid.UUID | None = None
    idempotent: bool = False


class CurriculumDocument(BaseModel):
    """Stable V1 portable schema; nested payload is validated by the import service."""

    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(default="gl-curriculum-v1", pattern="^gl-curriculum-v1$")
    curriculum_version: str = Field(min_length=1, max_length=80)
    course: dict[str, object]
    units: list[dict[str, object]] = Field(default_factory=list, max_length=200)
