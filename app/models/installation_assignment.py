import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InstallationAssignment(Base):
    __tablename__ = "installation_assignments"

    __table_args__ = (
        CheckConstraint(
            "status IN ('assigned', 'in_progress', 'submitted', 'completed', 'cancelled')",
            name="ck_installation_assignment_status",
        ),
        Index(
            "uq_installation_assignments_active_property",
            "property_id",
            unique=True,
            postgresql_where=text(
                "status IN ('assigned', 'in_progress', 'submitted')"
            ),
        ),
        Index(
            "uq_installation_assignments_active_plate",
            "plate_id",
            unique=True,
            postgresql_where=text(
                "status IN ('assigned', 'in_progress', 'submitted')"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("properties.id"),
        nullable=False,
        index=True,
    )

    plate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("address_plates.id"),
        nullable=False,
        index=True,
    )

    contractor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("contractors.id"),
        nullable=False,
        index=True,
    )

    contractor_member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("contractor_members.id"),
        nullable=False,
        index=True,
    )

    assigned_by: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="assigned",
    )

    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
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
