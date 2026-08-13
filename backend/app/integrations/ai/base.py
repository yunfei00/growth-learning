"""Business-facing AI provider contract."""

from typing import Literal, Protocol

from pydantic import BaseModel, Field


class AIMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class AICompletionRequest(BaseModel):
    messages: list[AIMessage] = Field(min_length=1)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=800, gt=0)
    json_response: bool = False


class AICompletionResponse(BaseModel):
    text: str
    provider: str
    model: str
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class AIProvider(Protocol):
    """The only AI surface application services should depend upon."""

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        """Generate a completion using a configured provider."""
        ...


class AIProviderError(RuntimeError):
    """Normalized provider failure exposed to application services."""
