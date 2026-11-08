from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.rate_limit import get_rate_limit_service
from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.runtime_config import validate_runtime_configuration
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_configuration()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    api_v1_router,
    prefix="/api/v1",
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


@app.get("/ready")
def readiness_check():
    """Report readiness when required dependencies are available."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "unavailable",
            },
        )

    if settings.environment.strip().lower() in {"staging", "production"}:
        if not get_rate_limit_service().check_store_health():
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "database": "ok",
                    "redis": "unavailable",
                },
            )
        return {
            "status": "ready",
            "database": "ok",
            "redis": "ok",
        }

    return {
        "status": "ready",
        "database": "ok",
    }
