"""Non-authoritative AI explanations for characters and completed science work."""

import json
import logging

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.integrations.ai.base import AICompletionRequest, AIMessage, AIProvider, AIProviderError
from app.models import ChineseCharacter, ExperimentSession
from app.schemas.learning import CharacterAIAssistanceResponse
from app.schemas.science import ExperimentAIParentTipResponse, ExperimentSessionResponse

logger = logging.getLogger(__name__)


class LearningAssistantError(RuntimeError):
    """A recoverable AI helper failure that must not interrupt learning."""


class _CharacterPayload(BaseModel):
    simple_explanation: str = Field(min_length=1, max_length=160)
    words: list[str] = Field(min_length=2, max_length=5)
    example_sentence: str = Field(min_length=1, max_length=120)
    parent_tip: str = Field(min_length=1, max_length=240)

    @field_validator("words")
    @classmethod
    def clean_words(cls, value: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if len(cleaned) < 2:
            raise ValueError("At least two distinct words are required")
        return cleaned


class _SciencePayload(BaseModel):
    parent_tip: str = Field(min_length=1, max_length=500)


async def generate_character_assistance(
    provider: AIProvider,
    character: ChineseCharacter,
) -> CharacterAIAssistanceResponse:
    contract = {
        "task": "为低龄儿童和家长辅助讲解一个汉字",
        "character": character.character,
        "pinyin": character.pinyin,
        "manual_context": {
            "simple_explanation": character.simple_meaning,
            "words": character.common_words,
            "example_sentence": character.example_sentence,
            "parent_tip": character.parent_tip,
        },
        "requirements": [
            "解释使用儿童能理解的短句，不把拼音作为主要理解方式",
            "组词必须包含目标汉字且适合儿童",
            "例句简短、自然、安全",
            "家长提示必须是可以在线下完成的具体讲解建议",
            "不要评价孩子掌握度，不要给分，不要输出学习记录建议",
        ],
        "json_schema": {
            "simple_explanation": "string",
            "words": ["string", "string", "string"],
            "example_sentence": "string",
            "parent_tip": "string",
        },
    }
    try:
        response = await provider.complete(
            AICompletionRequest(
                messages=[
                    AIMessage(
                        role="system",
                        content=(
                            "你是受控的儿童识字辅助讲解器。只返回严格 JSON，不返回 Markdown，"
                            "不索取儿童信息，不修改或判断学习状态。"
                        ),
                    ),
                    AIMessage(role="user", content=json.dumps(contract, ensure_ascii=False)),
                ],
                temperature=0.2,
                max_tokens=600,
                json_response=True,
            )
        )
        generated = _CharacterPayload.model_validate_json(response.text)
    except (AIProviderError, ValidationError) as error:
        logger.warning(
            "Character learning assistance failed",
            extra={"character": character.character},
            exc_info=True,
        )
        raise LearningAssistantError("AI 讲解暂时不可用，请继续使用页面原有内容") from error
    logger.info(
        "Character learning assistance generated",
        extra={"character": character.character, "provider": response.provider},
    )
    return CharacterAIAssistanceResponse(
        **generated.model_dump(),
        provider=response.provider,
        model=response.model,
    )


async def generate_science_parent_tip(
    provider: AIProvider,
    experiment_session: ExperimentSession,
    response_model: ExperimentSessionResponse,
) -> ExperimentAIParentTipResponse:
    evidence = [
        {"type": item.evidence_type, "text": item.original_text} for item in response_model.evidence
    ]
    snapshot = experiment_session.experiment_snapshot
    contract = {
        "task": "根据一次已经完成的家庭科学实验，给家长一段儿童友好的讲解建议",
        "experiment": {
            "title": snapshot.get("title"),
            "question": snapshot.get("guiding_question"),
            "phenomenon": snapshot.get("expected_phenomenon"),
            "scientific_explanation": snapshot.get("parent_scientific_explanation"),
        },
        "evidence": evidence,
        "requirements": [
            "尊重孩子原话，不评价能力，不给分",
            "用家长可以直接说出口的简短语言",
            "包含一个可以继续观察或追问的小建议",
            "不修改学习记录、测试或掌握度",
        ],
        "json_schema": {"parent_tip": "string"},
    }
    try:
        provider_response = await provider.complete(
            AICompletionRequest(
                messages=[
                    AIMessage(
                        role="system",
                        content=(
                            "你是家庭科学实验的辅助讲解器。只返回严格 JSON，不返回 Markdown，"
                            "不索取或猜测儿童个人信息。"
                        ),
                    ),
                    AIMessage(role="user", content=json.dumps(contract, ensure_ascii=False)),
                ],
                temperature=0.2,
                max_tokens=500,
                json_response=True,
            )
        )
        generated = _SciencePayload.model_validate_json(provider_response.text)
    except (AIProviderError, ValidationError) as error:
        logger.warning(
            "Science parent assistance failed",
            extra={"experiment_session_id": str(experiment_session.id)},
            exc_info=True,
        )
        raise LearningAssistantError("AI 家长建议暂时不可用，不影响实验档案") from error
    logger.info(
        "Science parent assistance generated",
        extra={
            "experiment_session_id": str(experiment_session.id),
            "provider": provider_response.provider,
        },
    )
    return ExperimentAIParentTipResponse(
        parent_tip=generated.parent_tip,
        provider=provider_response.provider,
        model=provider_response.model,
    )
