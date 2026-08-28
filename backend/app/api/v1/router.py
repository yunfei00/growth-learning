"""Version 1 API router."""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.characters import router as characters_router
from app.api.v1.children import router as children_router
from app.api.v1.courses import router as courses_router
from app.api.v1.english import admin_router as english_admin_router
from app.api.v1.english import router as english_router
from app.api.v1.experience import router as experience_router
from app.api.v1.families import router as families_router
from app.api.v1.family_collaboration import router as family_collaboration_router
from app.api.v1.growth import router as growth_router
from app.api.v1.learning import router as learning_router
from app.api.v1.math import admin_router as math_admin_router
from app.api.v1.math import router as math_router
from app.api.v1.pinyin import admin_router as pinyin_admin_router
from app.api.v1.pinyin import router as pinyin_router
from app.api.v1.platform_admin import router as platform_admin_router
from app.api.v1.science import router as science_router
from app.api.v1.science_admin import router as science_admin_router
from app.api.v1.stories import router as stories_router
from app.api.v1.teacher import router as teacher_router
from app.schemas.system import ApiInfoResponse

router = APIRouter(tags=["api"])
router.include_router(auth_router)
router.include_router(platform_admin_router)
router.include_router(admin_router)
router.include_router(pinyin_admin_router)
router.include_router(pinyin_router)
router.include_router(math_admin_router)
router.include_router(math_router)
router.include_router(english_admin_router)
router.include_router(english_router)
router.include_router(characters_router)
router.include_router(courses_router)
router.include_router(experience_router)
router.include_router(family_collaboration_router)
router.include_router(families_router)
router.include_router(growth_router)
router.include_router(learning_router)
router.include_router(science_admin_router)
router.include_router(science_router)
router.include_router(stories_router)
router.include_router(teacher_router)
router.include_router(children_router)


@router.get("", response_model=ApiInfoResponse)
@router.get("/", response_model=ApiInfoResponse, include_in_schema=False)
async def api_info() -> ApiInfoResponse:
    """Expose a small discovery response for the versioned API."""
    return ApiInfoResponse(name="Growth Learning API", version="v1")
