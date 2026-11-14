import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_platform_settings_singleton"),
        CheckConstraint(
            "length(currency_code) = 3 "
            "AND currency_code = upper(currency_code)",
            name="ck_platform_settings_currency_code",
        ),
        CheckConstraint(
            "time_format IN ('12h', '24h')",
            name="ck_platform_settings_time_format",
        ),
        CheckConstraint(
            "date_format IN ('DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD')",
            name="ck_platform_settings_date_format",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1,
    )

    organization_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Nestify",
    )

    legal_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    support_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    support_phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Africa/Nairobi",
    )

    locale: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="en-KE",
    )

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="KES",
    )

    date_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DD/MM/YYYY",
    )

    time_format: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="24h",
    )

    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
