import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EmailOutbox(Base):
    __tablename__ = "email_outbox"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'dead_letter')",
            name="ck_email_outbox_status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_email_outbox_attempt_count_nonnegative",
        ),
        CheckConstraint(
            "(status = 'processing' AND lease_id IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status != 'processing' AND lease_id IS NULL "
            "AND lease_expires_at IS NULL)",
            name="ck_email_outbox_lease_consistency",
        ),
        Index(
            "ix_email_outbox_status_next_attempt_at",
            "status",
            "next_attempt_at",
        ),
        Index(
            "ix_email_outbox_lease_expires_at",
            "lease_expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    employee_invitation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("employee_invitations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    encrypted_payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    encryption_key_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    lease_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        nullable=True,
    )

    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
