"""Science catalog, household inventory, experiment evidence, and private media contracts."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ScienceDifficultyValue = Literal["intro", "explore", "advanced"]
ScienceStatusValue = Literal["draft", "enabled", "archived"]
ExperimentSessionStatusValue = Literal["planned", "in_progress", "completed", "abandoned"]
ExperimentStepValue = Literal[
    "question",
    "prediction",
    "materials",
    "experiment",
    "observation",
    "explanation",
    "follow_up",
    "summary",
    "complete",
]
EvidenceTypeValue = Literal[
    "prediction",
    "observation",
    "child_summary",
    "question_asked",
    "child_original_words",
    "parent_explanation",
]
CapabilityTagValue = Literal[
    "observation",
    "questioning",
    "prediction",
    "hands_on",
    "causal_reasoning",
    "expression",
]
MediaKindValue = Literal["image", "video", "audio"]


def _clean_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Field cannot be blank")
    return value


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _clean_list(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class MaterialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    description: str | None = None
    unit: str | None = Field(default=None, max_length=40)
    category: str | None = Field(default=None, max_length=60)
    safety_note: str | None = None
    is_active: bool = True

    _normalize_name = field_validator("name")(_clean_required)
    _normalize_optional = field_validator("description", "unit", "category", "safety_note")(
        _clean_optional
    )
    _normalize_aliases = field_validator("aliases")(_clean_list)


class MaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_key: str
    name: str
    aliases: list[str]
    description: str | None
    unit: str | None
    category: str | None
    safety_note: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MaterialRequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: uuid.UUID | None = None
    material: MaterialCreate | None = None
    quantity_text: str | None = Field(default=None, max_length=120)
    is_required: bool = True
    substitution_notes: str | None = None
    position: int = Field(default=0, ge=0, le=100)

    _normalize_optional = field_validator("quantity_text", "substitution_notes")(_clean_optional)

    @model_validator(mode="after")
    def exactly_one_material_reference(self) -> "MaterialRequirementInput":
        if (self.material_id is None) == (self.material is None):
            raise ValueError("Provide exactly one of material_id or material")
        return self


class MaterialRequirementResponse(BaseModel):
    id: uuid.UUID
    material: MaterialResponse
    quantity_text: str | None
    is_required: bool
    substitution_notes: str | None
    position: int


class KnowledgePointLinkResponse(BaseModel):
    knowledge_point_id: uuid.UUID
    title: str
    character: str | None
    exposure_enabled: bool


class ScienceExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    age_min: int = Field(ge=0, le=18)
    age_max: int | None = Field(default=None, ge=0, le=18)
    difficulty: ScienceDifficultyValue
    estimated_duration_minutes: int = Field(gt=0, le=240)
    guiding_question: str = Field(min_length=1, max_length=1000)
    expected_phenomenon: str = Field(min_length=1, max_length=2000)
    child_friendly_explanation: str = Field(min_length=1, max_length=3000)
    parent_scientific_explanation: str = Field(min_length=1, max_length=5000)
    safety_notes: list[str] = Field(default_factory=list, max_length=20)
    common_failure_reasons: list[str] = Field(default_factory=list, max_length=20)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=10)
    likely_child_questions: list[str] = Field(default_factory=list, max_length=10)
    steps: list[str] = Field(min_length=1, max_length=20)
    status: ScienceStatusValue = "draft"
    source_type: Literal["system", "family"] = "system"
    requirements: list[MaterialRequirementInput] = Field(default_factory=list, max_length=30)
    related_knowledge_point_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)

    _normalize_required = field_validator(
        "title",
        "description",
        "guiding_question",
        "expected_phenomenon",
        "child_friendly_explanation",
        "parent_scientific_explanation",
    )(_clean_required)
    _normalize_lists = field_validator(
        "safety_notes",
        "common_failure_reasons",
        "follow_up_questions",
        "likely_child_questions",
        "steps",
    )(_clean_list)

    @model_validator(mode="after")
    def valid_age_range(self) -> "ScienceExperimentCreate":
        if self.age_max is not None and self.age_max < self.age_min:
            raise ValueError("age_max must be greater than or equal to age_min")
        return self


class ScienceExperimentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    age_min: int | None = Field(default=None, ge=0, le=18)
    age_max: int | None = Field(default=None, ge=0, le=18)
    difficulty: ScienceDifficultyValue | None = None
    estimated_duration_minutes: int | None = Field(default=None, gt=0, le=240)
    guiding_question: str | None = Field(default=None, min_length=1, max_length=1000)
    expected_phenomenon: str | None = Field(default=None, min_length=1, max_length=2000)
    child_friendly_explanation: str | None = Field(default=None, min_length=1, max_length=3000)
    parent_scientific_explanation: str | None = Field(default=None, min_length=1, max_length=5000)
    safety_notes: list[str] | None = Field(default=None, max_length=20)
    common_failure_reasons: list[str] | None = Field(default=None, max_length=20)
    follow_up_questions: list[str] | None = Field(default=None, max_length=10)
    likely_child_questions: list[str] | None = Field(default=None, max_length=10)
    steps: list[str] | None = Field(default=None, min_length=1, max_length=20)
    status: ScienceStatusValue | None = None
    requirements: list[MaterialRequirementInput] | None = Field(default=None, max_length=30)
    related_knowledge_point_ids: list[uuid.UUID] | None = Field(default=None, max_length=20)

    @field_validator(
        "title",
        "description",
        "guiding_question",
        "expected_phenomenon",
        "child_friendly_explanation",
        "parent_scientific_explanation",
    )
    @classmethod
    def normalize_required(cls, value: str | None) -> str | None:
        return None if value is None else _clean_required(value)

    @field_validator(
        "safety_notes",
        "common_failure_reasons",
        "follow_up_questions",
        "likely_child_questions",
        "steps",
    )
    @classmethod
    def normalize_lists(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_list(value)


class ScienceExperimentResponse(BaseModel):
    id: uuid.UUID
    canonical_key: str
    title: str
    description: str
    age_min: int
    age_max: int | None
    difficulty: ScienceDifficultyValue
    estimated_duration_minutes: int
    guiding_question: str
    expected_phenomenon: str
    child_friendly_explanation: str
    parent_scientific_explanation: str
    safety_notes: list[str]
    common_failure_reasons: list[str]
    follow_up_questions: list[str]
    likely_child_questions: list[str]
    steps: list[str]
    status: ScienceStatusValue
    source_type: Literal["system", "family"]
    content_version: int
    requirements: list[MaterialRequirementResponse]
    related_knowledge_points: list[KnowledgePointLinkResponse]
    created_at: datetime
    updated_at: datetime


class ScienceExperimentPage(BaseModel):
    items: list[ScienceExperimentResponse]
    page: int
    page_size: int
    total: int
    pages: int


class ScienceImportReport(BaseModel):
    created: int
    updated: int
    skipped: int
    materials_created: int
    errors: list[str]


class FamilyMaterialUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: uuid.UUID
    is_owned: bool
    quantity_text: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=1000)

    _normalize_optional = field_validator("quantity_text", "note")(_clean_optional)


class FamilyMaterialBatchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FamilyMaterialUpdate] = Field(min_length=1, max_length=100)


class FamilyMaterialResponse(BaseModel):
    material: MaterialResponse
    is_owned: bool
    quantity_text: str | None
    note: str | None
    updated_at: datetime | None


class ExperimentRecommendationResponse(BaseModel):
    experiment: ScienceExperimentResponse
    ready_at_home: bool
    owned_required_materials: list[str]
    missing_required_materials: list[str]
    optional_substitutions: list[str]
    reasons: list[str]
    recently_completed: bool


class ExperimentSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: uuid.UUID
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)
    request_key: str | None = Field(default=None, min_length=8, max_length=80)
    start_immediately: bool = True


class ExperimentSessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["start", "advance", "abandon"] | None = None
    current_step: ExperimentStepValue | None = None
    parent_note: str | None = Field(default=None, max_length=2000)

    _normalize_note = field_validator("parent_note")(_clean_optional)


class ExperimentEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: EvidenceTypeValue
    original_text: str = Field(min_length=1, max_length=4000)
    capability_tags: list[CapabilityTagValue] = Field(default_factory=list, max_length=6)
    client_key: str | None = Field(default=None, min_length=8, max_length=80)

    @field_validator("capability_tags")
    @classmethod
    def unique_tags(cls, value: list[CapabilityTagValue]) -> list[CapabilityTagValue]:
        return list(dict.fromkeys(value))


class ExperimentEvidenceBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ExperimentEvidenceInput] = Field(min_length=1, max_length=20)


class ExperimentEvidenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_text: str | None = Field(default=None, min_length=1, max_length=4000)
    capability_tags: list[CapabilityTagValue] | None = Field(default=None, max_length=6)

    @field_validator("original_text")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("capability_tags")
    @classmethod
    def unique_optional_tags(
        cls, value: list[CapabilityTagValue] | None
    ) -> list[CapabilityTagValue] | None:
        return None if value is None else list(dict.fromkeys(value))

    @model_validator(mode="after")
    def require_change(self) -> "ExperimentEvidenceUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one evidence field")
        return self


class ExperimentEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evidence_type: EvidenceTypeValue
    original_text: str
    capability_tags: list[CapabilityTagValue]
    recorder_user_id: uuid.UUID
    captured_at: datetime
    derived_summary: str | None
    derived_provider: str | None
    derived_model: str | None
    derived_version: str | None


class ExperimentMediaResponse(BaseModel):
    id: uuid.UUID
    media_kind: MediaKindValue
    mime_type: str
    size_bytes: int
    original_filename: str
    uploader_user_id: uuid.UUID
    created_at: datetime
    content_url: str


class ExperimentSessionResponse(BaseModel):
    id: uuid.UUID
    child_id: uuid.UUID
    experiment_id: uuid.UUID
    experiment_version_id: uuid.UUID
    experiment_snapshot: dict[str, object]
    accompanying_user_id: uuid.UUID
    status: ExperimentSessionStatusValue
    current_step: ExperimentStepValue
    local_date: date
    timezone: str
    started_at: datetime | None
    completed_at: datetime | None
    parent_note: str | None
    evidence: list[ExperimentEvidenceResponse]
    media: list[ExperimentMediaResponse]
    science_exposure_count: int
    created_at: datetime
    updated_at: datetime


class ExperimentSessionPage(BaseModel):
    items: list[ExperimentSessionResponse]
    page: int
    page_size: int
    total: int
    pages: int


class ExperimentCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_note: str | None = Field(default=None, max_length=2000)

    _normalize_note = field_validator("parent_note")(_clean_optional)


class ExperimentStoryGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    difficulty: Literal["beginner", "normal", "challenge"] = "normal"
    target_knowledge_point_ids: list[uuid.UUID] | None = Field(
        default=None, min_length=2, max_length=5
    )
    request_key: str | None = Field(default=None, min_length=8, max_length=80)


class ExperimentGrowthCardResponse(BaseModel):
    session_id: uuid.UUID
    title: str
    completed_at: datetime
    accompanying_user: str
    prediction: list[str]
    observation: list[str]
    child_original_words: list[str]
    child_summary: list[str]
    questions_asked: list[str]
    media: list[ExperimentMediaResponse]
    scientific_explanation: str
    follow_up_questions: list[str]
    related_characters: list[str]
    capability_tags: list[CapabilityTagValue]


class ExperimentAIParentTipResponse(BaseModel):
    parent_tip: str
    provider: str
    model: str
    learning_records_modified: Literal[False] = False
