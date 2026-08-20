"""Application liveness endpoint."""

from fastapi import APIRouter, Request

from app.schemas.system import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Report process liveness without depending on external services."""
    settings = request.app.state.settings
    revision = settings.app_revision.strip() or "unknown"
    return HealthResponse(status="ok", version=settings.app_version, revision=revision[:12])
