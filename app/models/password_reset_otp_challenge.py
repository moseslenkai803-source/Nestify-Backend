import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PasswordResetOtpChallenge(Base):
    __tablename__ = "password_reset_otp_challenges"

    __table_args__ = (
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 5",
            name="ck_password_reset_otp_attempt_count",
        ),
        CheckConstraint(
            "(reset_grant_hash IS NULL AND "
            "reset_grant_expires_at IS NULL) OR "
            "(reset_grant_hash IS NOT NULL AND "
            "reset_grant_expires_at IS NOT NULL)",
            name="ck_password_reset_otp_grant_consistency",
        ),
        UniqueConstraint(
            "reset_grant_hash",
            name="uq_password_reset_otp_grant_hash",
        ),
        Index(
            "ix_password_reset_otp_user_consumed_created",
            "user_id",
            "consumed_at",
            "created_at",
        ),
        Index(
            "ix_password_reset_otp_expires_at",
            "expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    otp_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reset_grant_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    reset_grant_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
