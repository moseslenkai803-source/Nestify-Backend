import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PropertyLocationVerification(Base):
    __tablename__ = "property_location_verifications"

    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="ck_property_location_verifications_decision",
        ),
        # A location version receives one final decision; later submissions
        # create new versions instead of rewriting this evidence.
        UniqueConstraint(
            "location_id",
            name="uq_property_location_verifications_location",
        ),
        Index(
            "ix_property_location_verifications_verified_by",
            "verified_by",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("property_locations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    verified_by: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    verification_method: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
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
