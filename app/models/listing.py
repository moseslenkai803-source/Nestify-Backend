import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Listing(Base):
    __tablename__ = "listings"

    __table_args__ = (
        CheckConstraint(
            """
            (
                (property_id IS NOT NULL)::integer +
                (floor_id IS NOT NULL)::integer +
                (space_id IS NOT NULL)::integer
            ) = 1
            """,
            name="ck_listings_exactly_one_target",
        ),
        CheckConstraint(
            "transaction_type IN ('sale', 'rent')",
            name="ck_listings_transaction_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'unpublished')",
            name="ck_listings_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    property_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("properties.id"),
        nullable=True,
        index=True,
    )

    floor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("floors.id"),
        nullable=True,
        index=True,
    )

    space_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("spaces.id"),
        nullable=True,
        index=True,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
