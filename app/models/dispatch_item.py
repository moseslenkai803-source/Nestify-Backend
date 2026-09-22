import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DispatchItem(Base):
    __tablename__ = "dispatch_items"

    __table_args__ = (
        Index(
            "uq_dispatch_items_active_plate_id",
            "plate_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("dispatches.id"),
        nullable=False,
        index=True,
    )

    plate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("address_plates.id"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
