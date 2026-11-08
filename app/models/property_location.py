import uuid
from datetime import UTC, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PropertyLocation(Base):
    __tablename__ = "property_locations"

    __table_args__ = (
        CheckConstraint(
            "version_number > 0",
            name="ck_property_locations_version_number_positive",
        ),
        CheckConstraint(
            "latitude BETWEEN -90 AND 90",
            name="ck_property_locations_latitude_range",
        ),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name="ck_property_locations_longitude_range",
        ),
        CheckConstraint(
            "accuracy_meters IS NULL OR "
            "(accuracy_meters >= 0 AND "
            "accuracy_meters < 'Infinity'::double precision)",
            name="ck_property_locations_accuracy_finite_nonnegative",
        ),
        CheckConstraint(
            "status IN ('unverified', 'pending', 'approved', 'rejected')",
            name="ck_property_locations_status",
        ),
        CheckConstraint(
            "NOT is_current OR status = 'approved'",
            name="ck_property_locations_current_requires_approval",
        ),
        UniqueConstraint(
            "property_id",
            "version_number",
            name="uq_property_locations_property_version",
        ),
        Index(
            "ix_property_locations_property_id",
            "property_id",
        ),
        # Keep history, but allow only one unresolved submission and one
        # location selected as current for each property.
        Index(
            "uq_property_locations_one_pending_per_property",
            "property_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "uq_property_locations_one_current_per_property",
            "property_id",
            unique=True,
            postgresql_where=text("is_current IS TRUE"),
        ),
        Index(
            "idx_property_locations_location",
            "location",
            postgresql_using="gist",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("properties.id", ondelete="RESTRICT"),
        nullable=False,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    latitude: Mapped[float] = mapped_column(
        nullable=False,
    )

    longitude: Mapped[float] = mapped_column(
        nullable=False,
    )

    location = mapped_column(
        Geometry(
            geometry_type="POINT",
            srid=4326,
            spatial_index=False,
        ),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    capture_method: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    accuracy_meters: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="unverified",
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
