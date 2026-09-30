import uuid
from datetime import datetime, UTC

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PropertyAddress(Base):
    __tablename__ = "property_addresses"

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

    formatted_address: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    county: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    sub_county: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    locality: Mapped[str | None] = mapped_column(
        String(150),
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