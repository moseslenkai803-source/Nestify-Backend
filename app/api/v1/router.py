from fastapi import APIRouter

from app.api.v1.address_plates import router as address_plates_router
from app.api.v1.address_plate_requests import router as address_plate_requests_router
from app.api.v1.auth import router as auth_router
from app.api.v1.properties import router as properties_router
from app.api.v1.buildings import router as buildings_router
from app.api.v1.manufacturing_orders import router as manufacturing_orders_router


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
    buildings_router,
)
router.include_router(
    address_plates_router,
)
router.include_router(
    address_plate_requests_router,
)
router.include_router(
    auth_router,
)
router.include_router(
    manufacturing_orders_router,
)
