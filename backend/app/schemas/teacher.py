"""Narrow DTOs for parent-authorized teacher collaboration."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.learning import AssessmentItemInput, MasteryLevelValue

TeacherStatusValue = Literal["active", "disabled"]
RelationStatusValue = Literal["active", "revoked"]
ClassroomStatusValue = Literal["active", "archived"]
MembershipStatusValue = Literal["active", "left"]
AssignmentTypeValue = Literal[
    "character_learning",
    "character_review",
    "recognition_check",
    "reading",
    "freeform_instruction",
]
AssignmentStatusValue = Literal["draft", "published", "closed", "archived"]
ProgressStatusValue = Literal["pending", "in_progress", "completed", "overdue"]
ObservationCategoryValue = Literal[
    "recognition", "reading", "expression", "learning_habit", "participation", "other"
]


class TeacherProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=80)
    organization_name: str | None = Field(default=None, max_length=120)
    short_bio: str | None = Field(default=None, max_length=300)


class TeacherProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    organization_name: str | None = Field(default=None, max_length=120)
    short_bio: str | None = Field(default=None, max_length=300)


class TeacherProfileResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    organization_name: str | None
    short_bio: str | None
    teacher_code: str
    status: TeacherStatusValue
    created_at: datetime
    updated_at: datetime


class TeacherPublicProfile(BaseModel):
    id: uuid.UUID
    display_name: str
    organization_name: str | None
    short_bio: str | None


class ClassroomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=300)


class ClassroomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    status: ClassroomStatusValue | None = None


class ClassroomResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    class_code: str
    status: ClassroomStatusValue
    student_count: int
    created_at: datetime
    updated_at: datetime


class ConnectionResolveResponse(BaseModel):
    kind: Literal["teacher", "classroom"]
    teacher: TeacherPublicProfile
    classroom: ClassroomResponse | None = None


class ParentConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=12, max_length=64)


class TeacherRelationResponse(BaseModel):
    id: uuid.UUID
    child_id: uuid.UUID
    teacher: TeacherPublicProfile
    status: RelationStatusValue
    authorized_at: datetime
    revoked_at: datetime | None
    permission_version: str


class ClassroomMembershipResponse(BaseModel):
    id: uuid.UUID
    classroom_id: uuid.UUID
    classroom_name: str
    teacher: TeacherPublicProfile
    status: MembershipStatusValue
    joined_at: datetime
    left_at: datetime | None


class AssignmentCharacter(BaseModel):
    knowledge_point_id: uuid.UUID
    character: str
    pinyin: str
    position: int


class AssignmentTargetSummary(BaseModel):
    child_id: uuid.UUID
    child_name: str
    progress_status: ProgressStatusValue
    completed_item_count: int
    total_item_count: int


class TeacherAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classroom_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=160)
    instructions: str = Field(min_length=1, max_length=2000)
    assignment_type: AssignmentTypeValue
    due_at: datetime | None = None
    target_child_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    knowledge_point_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_content(self) -> "TeacherAssignmentCreate":
        if len(self.target_child_ids) != len(set(self.target_child_ids)):
            raise ValueError("A child may appear only once")
        if len(self.knowledge_point_ids) != len(set(self.knowledge_point_ids)):
            raise ValueError("A knowledge point may appear only once")
        is_character = self.assignment_type in {
            "character_learning",
            "character_review",
            "recognition_check",
        }
        if is_character and not self.knowledge_point_ids:
            raise ValueError("Character assignments require knowledge points")
        if not self.target_child_ids and self.classroom_id is None:
            raise ValueError("Select children or a classroom")
        return self


class TeacherAssignmentResponse(BaseModel):
    id: uuid.UUID
    teacher: TeacherPublicProfile
    classroom_id: uuid.UUID | None
    classroom_name: str | None
    title: str
    instructions: str
    assignment_type: AssignmentTypeValue
    due_at: datetime | None
    status: AssignmentStatusValue
    published_at: datetime | None
    characters: list[AssignmentCharacter]
    targets: list[AssignmentTargetSummary]
    created_at: datetime
    updated_at: datetime


class TeacherTaskListItem(BaseModel):
    assignment_id: uuid.UUID
    teacher: TeacherPublicProfile
    classroom_name: str | None
    title: str
    instructions: str
    assignment_type: AssignmentTypeValue
    due_at: datetime | None
    progress_status: ProgressStatusValue
    completed_item_count: int
    total_item_count: int
    characters: list[AssignmentCharacter]


class TeacherTaskProgressResponse(TeacherTaskListItem):
    learning_session_id: uuid.UUID | None
    assessment_session_id: uuid.UUID | None
    reading_session_id: uuid.UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    completed_learning_point_ids: list[uuid.UUID]
    assessment_outcomes: dict[str, str]


class TeacherTaskSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_point_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    assessment_items: list[AssessmentItemInput] = Field(default_factory=list, max_length=50)
    reading_session_id: uuid.UUID | None = None
    complete: bool = False

    @model_validator(mode="after")
    def unique_items(self) -> "TeacherTaskSubmission":
        if len(self.learning_point_ids) != len(set(self.learning_point_ids)):
            raise ValueError("A knowledge point may appear only once")
        assessment_ids = [item.knowledge_point_id for item in self.assessment_items]
        if len(assessment_ids) != len(set(assessment_ids)):
            raise ValueError("An assessment item may appear only once")
        if not (
            self.learning_point_ids
            or self.assessment_items
            or self.reading_session_id
            or self.complete
        ):
            raise ValueError("Submit progress or complete the task")
        return self


class TeacherObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ObservationCategoryValue
    original_text: str = Field(min_length=1, max_length=2000)
    occurred_at: datetime
    classroom_id: uuid.UUID | None = None
    assignment_id: uuid.UUID | None = None
    knowledge_point_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class TeacherObservationResponse(BaseModel):
    id: uuid.UUID
    teacher: TeacherPublicProfile
    child_id: uuid.UUID
    category: ObservationCategoryValue
    original_text: str
    occurred_at: datetime
    classroom_id: uuid.UUID | None
    assignment_id: uuid.UUID | None
    knowledge_point_ids: list[uuid.UUID]
    created_at: datetime


class TeacherStudentMastery(BaseModel):
    knowledge_point_id: uuid.UUID
    character: str
    pinyin: str
    mastery_level: MasteryLevelValue
    mastery_score: float
    is_priority: bool


class TeacherStudentSummary(BaseModel):
    child_id: uuid.UUID
    display_name: str
    nickname: str | None
    age_band: str
    assignments: list[TeacherTaskListItem]
    relevant_mastery: list[TeacherStudentMastery]
    observations: list[TeacherObservationResponse]


class AssignmentAnalytics(BaseModel):
    assignment_id: uuid.UUID
    total: int
    pending: int
    in_progress: int
    completed: int
    overdue: int
    outcome_counts: dict[str, int]
    character_outcomes: dict[str, dict[str, int]]
    common_errors: list[str]
    ranking_enabled: Literal[False] = False


class ParentTeacherCollaboration(BaseModel):
    relations: list[TeacherRelationResponse]
    classrooms: list[ClassroomMembershipResponse]
    assignments: list[TeacherTaskListItem]
    observations: list[TeacherObservationResponse]


class TeacherDashboard(BaseModel):
    profile: TeacherProfileResponse
    classrooms: list[ClassroomResponse]
    students: list[TeacherStudentSummary]
    assignments: list[TeacherAssignmentResponse]
    pending_review_count: int
    recent_completed_count: int
