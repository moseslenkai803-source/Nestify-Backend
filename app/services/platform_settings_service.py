from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.platform_setting import PlatformSetting
from app.models.platform_setting_audit_log import PlatformSettingAuditLog
from app.schemas.platform_settings import PlatformSettingUpdate


class PlatformSettingsService:
    SETTING_ID = 1

    NULLABLE_FIELDS = {
        "legal_name",
        "support_email",
        "support_phone",
    }

    def __init__(self, db: Session):
        self.db = db

    def get_settings(self) -> PlatformSetting:
        statement = select(PlatformSetting).where(
            PlatformSetting.id == self.SETTING_ID
        )
        setting = self.db.scalar(statement)

        if setting is None:
            raise RuntimeError(
                "Platform settings singleton is missing; verify the Settings migration"
            )

        return setting

    def update_settings(
        self,
        payload: PlatformSettingUpdate,
        actor_user_id: UUID,
    ) -> PlatformSetting:
        statement = (
            select(PlatformSetting)
            .where(PlatformSetting.id == self.SETTING_ID)
            .with_for_update()
        )
        setting = self.db.scalar(statement)

        if setting is None:
            raise RuntimeError(
                "Platform settings singleton is missing; verify the Settings migration"
            )

        changes = payload.model_dump(
            exclude_unset=True,
            exclude={"reason"},
        )
        # Validate and normalize all submitted fields before mutating the ORM object.
        normalized_changes = {}
        for key, submitted_value in changes.items():
            if submitted_value is None and key not in self.NULLABLE_FIELDS:
                raise ValueError(f"{key} cannot be null")

            new_value = submitted_value
            if isinstance(new_value, str):
                new_value = new_value.strip()
            if key in self.NULLABLE_FIELDS and new_value == "":
                new_value = None
            normalized_changes[key] = new_value

        reason = payload.reason.strip() if payload.reason else None
        changed_at = datetime.now(UTC)
        audit_entries: list[PlatformSettingAuditLog] = []

        for key, new_value in normalized_changes.items():
            previous_value = getattr(setting, key)

            if previous_value == new_value:
                continue

            audit_entries.append(
                PlatformSettingAuditLog(
                    actor_user_id=actor_user_id,
                    setting_key=key,
                    previous_value=(
                        str(previous_value) if previous_value is not None else None
                    ),
                    new_value=str(new_value) if new_value is not None else None,
                    reason=reason,
                    changed_at=changed_at,
                )
            )
            setattr(setting, key, new_value)

        if audit_entries:
            setting.updated_by = actor_user_id
            setting.updated_at = changed_at
            self.db.add_all(audit_entries)

        # The request-scoped get_db dependency owns commit and rollback.
        # Flush here so constraint errors occur before the service returns.
        self.db.flush()

        return setting

    def list_audit_logs(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PlatformSettingAuditLog]:
        statement = (
            select(PlatformSettingAuditLog)
            .order_by(
                desc(PlatformSettingAuditLog.changed_at),
                desc(PlatformSettingAuditLog.id),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())
