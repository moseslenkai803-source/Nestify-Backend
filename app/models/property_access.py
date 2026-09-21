import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PropertyAccess(Base):
    __tablename__ = "property_access"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "property_id",
            "access_type",
            name="uq_property_access_user_property_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    property_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("properties.id"),
        nullable=False,
        index=True,
    )

    access_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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
