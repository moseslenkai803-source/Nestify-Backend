import uuid
from datetime import datetime, UTC

from sqlalchemy import DateTime, ForeignKey, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Space(Base):
    __tablename__ = "spaces"

    __table_args__ = (
        UniqueConstraint(
            "floor_id",
            "space_number",
            name="uq_space_floor_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    floor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("floors.id"),
        nullable=False,
        index=True,
    )

    space_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    space_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="general",
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
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
