from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.api.rate_limit import get_rate_limit_service
from app.core.config import settings
from app.db.session import get_db
from app.models.email_outbox import EmailOutbox
from app.models.user import User
from app.schemas.platform_settings import (
    EmailOutboxCounts,
    PlatformSettingAuditResponse,
    PlatformSettingResponse,
    PlatformSettingUpdate,
    PlatformSettingsStatusResponse,
    SafeRuntimeConfiguration,
)
from app.services.email_service import EmailService
from app.services.platform_settings_service import PlatformSettingsService


router = APIRouter(prefix="/settings", tags=["Platform Settings"])


@router.get("", response_model=PlatformSettingResponse)
def get_platform_settings(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db, scope="function"),
):
    try:
        return PlatformSettingsService(db).get_settings()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Platform settings are unavailable",
        ) from exc


@router.patch("", response_model=PlatformSettingResponse)
def update_platform_settings(
    payload: PlatformSettingUpdate,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db, scope="function"),
):
    try:
        return PlatformSettingsService(db).update_settings(
            payload,
            current_admin.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Platform settings are unavailable",
        ) from exc


@router.get(
    "/audit-logs",
    response_model=list[PlatformSettingAuditResponse],
)
def list_platform_settings_audit_logs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db, scope="function"),
):
    return PlatformSettingsService(db).list_audit_logs(
        limit=limit,
        offset=offset,
    )


@router.get("/status", response_model=PlatformSettingsStatusResponse)
def get_platform_settings_status(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db, scope="function"),
):
    database_status = "healthy"
    outbox_counts = None

    try:
        db.execute(text("SELECT 1"))
        grouped_counts = db.execute(
            select(EmailOutbox.status, func.count(EmailOutbox.id)).group_by(
                EmailOutbox.status
            )
        ).all()

        counts = {status: count for status, count in grouped_counts}
        outbox_counts = EmailOutboxCounts(
            pending=counts.get("pending", 0),
            processing=counts.get("processing", 0),
            sent=counts.get("sent", 0),
            dead_letter=counts.get("dead_letter", 0),
        )
    except SQLAlchemyError:
        db.rollback()
        database_status = "unavailable"
        outbox_counts = None

    environment = settings.environment.strip().lower()

    if environment in {"staging", "production"}:
        try:
            redis_status = (
                "healthy"
                if get_rate_limit_service().check_store_health()
                else "unavailable"
            )
        except Exception:
            redis_status = "unavailable"
    else:
        redis_status = "not_required"

    encryption_keys = settings.outbox_encryption_keys
    active_key_version = settings.outbox_active_encryption_key_version

    return PlatformSettingsStatusResponse(
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=environment,
        database_status=database_status,
        redis_status=redis_status,
        email_configuration_status=(
            "configured" if EmailService.is_configured() else "not_configured"
        ),
        outbox_counts=outbox_counts,
        runtime_configuration=SafeRuntimeConfiguration(
            debug_mode=settings.debug,
            frontend_url_configured=bool(settings.frontend_base_url),
            cors_origin_count=len(settings.cors_allowed_origins),
            jwt_secret_configured=bool(settings.jwt_secret_key.strip()),
            outbox_encryption_configured=bool(
                encryption_keys
                and active_key_version
                and active_key_version in encryption_keys
            ),
        ),
    )
