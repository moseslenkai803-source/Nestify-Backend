from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

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
    """Report readiness only when the database can execute a query."""
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

    return {
        "status": "ready",
        "database": "ok",
    }
