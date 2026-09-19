from fastapi import FastAPI

from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)


@app.get("/")
def root():
    return {
        "message": "Nestify Backend is running",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
    }