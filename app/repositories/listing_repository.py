from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.listing import Listing


class ListingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(
        self,
        listing_id: UUID,
    ) -> Listing | None:
        return self.db.scalar(
            select(Listing).where(
                Listing.id == listing_id,
            )
        )

    def get_by_id_for_update(
        self,
        listing_id: UUID,
    ) -> Listing | None:
        statement = (
            select(Listing)
            .where(Listing.id == listing_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        return self.db.scalar(statement)

    def get_by_property_id(
        self,
        property_id: UUID,
    ) -> list[Listing]:
        return self.db.scalars(
            select(Listing)
            .where(Listing.property_id == property_id)
            .order_by(Listing.created_at.asc(), Listing.id.asc())
        ).all()

    def get_by_floor_id(
        self,
        floor_id: UUID,
    ) -> list[Listing]:
        return self.db.scalars(
            select(Listing)
            .where(Listing.floor_id == floor_id)
            .order_by(Listing.created_at.asc(), Listing.id.asc())
        ).all()

    def get_by_space_id(
        self,
        space_id: UUID,
    ) -> list[Listing]:
        return self.db.scalars(
            select(Listing)
            .where(Listing.space_id == space_id)
            .order_by(Listing.created_at.asc(), Listing.id.asc())
        ).all()

    def add(
        self,
        listing: Listing,
    ) -> Listing:
        self.db.add(listing)
        self.db.flush()
        return listing

    def flush(self) -> None:
        self.db.flush()
