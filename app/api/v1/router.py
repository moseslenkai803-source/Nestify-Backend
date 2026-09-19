from fastapi import APIRouter


router = APIRouter()

@router.get("/health")
def api_health_check():
    return {
        "status": "ok",
        "api_version": "v1",
    }