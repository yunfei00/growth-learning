"""Version 1 API router."""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.characters import router as characters_router
from app.api.v1.children import router as children_router
from app.api.v1.families import router as families_router
from app.api.v1.learning import router as learning_router
from app.api.v1.science import router as science_router
from app.api.v1.science_admin import router as science_admin_router
from app.api.v1.stories import router as stories_router
from app.schemas.system import ApiInfoResponse

router = APIRouter(tags=["api"])
router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(characters_router)
router.include_router(families_router)
router.include_router(learning_router)
router.include_router(science_admin_router)
router.include_router(science_router)
router.include_router(stories_router)
router.include_router(children_router)


@router.get("", response_model=ApiInfoResponse)
@router.get("/", response_model=ApiInfoResponse, include_in_schema=False)
async def api_info() -> ApiInfoResponse:
    """Expose a small discovery response for the versioned API."""
    return ApiInfoResponse(name="Growth Learning API", version="v1")
