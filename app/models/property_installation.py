import uuid
from datetime import datetime, UTC

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PropertyInstallation(Base):
    __tablename__ = "property_installations"

    __table_args__ = (
        CheckConstraint(
            "latitude BETWEEN -90 AND 90",
            name="ck_property_installations_latitude_range",
        ),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name="ck_property_installations_longitude_range",
        ),
        CheckConstraint(
            "accuracy_meters IS NULL OR "
            "(accuracy_meters >= 0 AND "
            "accuracy_meters < 'Infinity'::double precision)",
            name="ck_property_installations_accuracy_finite_nonnegative",
        ),
        Index(
            "uq_property_installations_one_submitted_per_property",
            "property_id",
            unique=True,
            postgresql_where=text("status = 'submitted'"),
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

    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("installation_assignments.id"),
        nullable=True,
        index=True,
    )

    installer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    accuracy_meters: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="submitted",
    )

    notes: Mapped[str | None] = mapped_column(
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
