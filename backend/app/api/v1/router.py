"""Version 1 API router."""

from fastapi import APIRouter

from app.schemas.system import ApiInfoResponse

router = APIRouter(tags=["api"])


@router.get("", response_model=ApiInfoResponse)
@router.get("/", response_model=ApiInfoResponse, include_in_schema=False)
async def api_info() -> ApiInfoResponse:
    """Expose a small discovery response for the versioned API."""
    return ApiInfoResponse(name="Growth Learning API", version="v1")
