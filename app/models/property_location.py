import uuid
from datetime import UTC, datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PropertyLocation(Base):
    __tablename__ = "property_locations"

    __table_args__ = (
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
        ForeignKey("properties.id"),
        unique=True,
        nullable=False,
        index=True,
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
