from fastapi import APIRouter

from app.api.v1.address_plates import router as address_plates_router
from app.api.v1.properties import router as properties_router


router = APIRouter()


@router.get("/health")
def api_health_check():
    return {
        "status": "ok",
        "api_version": "v1",
    }


router.include_router(
    properties_router,
)
router.include_router(
    address_plates_router,
)
