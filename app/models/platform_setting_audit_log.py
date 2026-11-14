import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlatformSettingAuditLog(Base):
    __tablename__ = "platform_setting_audit_logs"

    __table_args__ = (
        Index(
            "ix_platform_setting_audit_logs_changed_at",
            "changed_at",
        ),
        Index(
            "ix_platform_setting_audit_logs_setting_key",
            "setting_key",
        ),
        Index(
            "ix_platform_setting_audit_logs_actor_user_id",
            "actor_user_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    setting_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    previous_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    new_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
