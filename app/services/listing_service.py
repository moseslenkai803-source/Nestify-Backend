import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.property_actions import PropertyAction
from app.models.listing import Listing
from app.models.user import User
from app.repositories.building_repository import BuildingRepository
from app.repositories.floor_repository import FloorRepository
from app.repositories.listing_repository import ListingRepository
from app.repositories.space_repository import SpaceRepository
from app.services.property_authorization_service import (
    PropertyAuthorizationService,
)


class ListingService:
    def __init__(self, db: Session):
        self.listing_repository = ListingRepository(db)
        self.building_repository = BuildingRepository(db)
        self.floor_repository = FloorRepository(db)
        self.space_repository = SpaceRepository(db)
        self.property_authorization_service = PropertyAuthorizationService(db)

    @staticmethod
    def _validate_transaction_type(transaction_type: str) -> None:
        if transaction_type not in {"sale", "rent"}:
            raise ValueError("Invalid transaction type")

    def create_property_listing(
        self,
        user: User,
        property_id: uuid.UUID,
        transaction_type: str,
        title: str,
        description: str | None = None,
    ) -> Listing:
        self._validate_transaction_type(transaction_type)

        property = self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        listing = Listing(
            property_id=property.id,
            transaction_type=transaction_type,
            title=title,
            description=description,
            status="draft",
        )

        return self.listing_repository.add(listing)

    def create_floor_listing(
        self,
        user: User,
        property_id: uuid.UUID,
        building_id: uuid.UUID,
        floor_id: uuid.UUID,
        transaction_type: str,
        title: str,
        description: str | None = None,
    ) -> Listing:
        self._validate_transaction_type(transaction_type)

        floor = self.floor_repository.get_by_id(floor_id)

        if floor is None:
            raise ValueError("Floor not found")

        building = self.building_repository.get_by_id(floor.building_id)

        if building is None:
            raise ValueError("Building not found")

        if building.id != building_id:
            raise ValueError("Floor not found")

        if building.property_id != property_id:
            raise ValueError("Floor not found")

        property = self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        listing = Listing(
            floor_id=floor.id,
            transaction_type=transaction_type,
            title=title,
            description=description,
            status="draft",
        )

        return self.listing_repository.add(listing)

    def create_space_listing(
        self,
        user: User,
        property_id: uuid.UUID,
        building_id: uuid.UUID,
        floor_id: uuid.UUID,
        space_id: uuid.UUID,
        transaction_type: str,
        title: str,
        description: str | None = None,
    ) -> Listing:
        self._validate_transaction_type(transaction_type)

        space = self.space_repository.get_by_id(space_id)

        if space is None:
            raise ValueError("Space not found")

        floor = self.floor_repository.get_by_id(space.floor_id)

        if floor is None:
            raise ValueError("Floor not found")

        if floor.id != floor_id:
            raise ValueError("Space not found")

        building = self.building_repository.get_by_id(floor.building_id)

        if building is None:
            raise ValueError("Building not found")

        if building.id != building_id:
            raise ValueError("Space not found")

        if building.property_id != property_id:
            raise ValueError("Space not found")

        self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        listing = Listing(
            space_id=space.id,
            transaction_type=transaction_type,
            title=title,
            description=description,
            status="draft",
        )

        return self.listing_repository.add(listing)

    def publish_listing(
        self,
        user: User,
        listing_id: uuid.UUID,
    ) -> Listing:
        listing = self.listing_repository.get_by_id_for_update(listing_id)

        if listing is None:
            raise ValueError("Listing not found")

        property_id = self._get_listing_property_id(listing)

        property = self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        if property.status != "active":
            raise ValueError(
                "Property must be active before listing can be published"
            )

        if listing.status == "published":
            raise ValueError("Listing is already published")

        if listing.status not in {"draft", "unpublished"}:
            raise ValueError("Listing cannot be published from its current status")

        listing.status = "published"
        listing.published_at = datetime.now(UTC)

        self.listing_repository.flush()

        return listing

    def unpublish_listing(
        self,
        user: User,
        listing_id: uuid.UUID,
    ) -> Listing:
        listing = self.listing_repository.get_by_id_for_update(listing_id)

        if listing is None:
            raise ValueError("Listing not found")

        property_id = self._get_listing_property_id(listing)

        self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        if listing.status != "published":
            raise ValueError("Listing is not published")

        listing.status = "unpublished"
        listing.published_at = None

        self.listing_repository.flush()

        return listing

    def _get_listing_property_id(
        self,
        listing: Listing,
    ) -> uuid.UUID:
        if listing.property_id is not None:
            return listing.property_id

        if listing.floor_id is not None:
            floor = self.floor_repository.get_by_id(listing.floor_id)

            if floor is None:
                raise ValueError("Floor not found")

            building = self.building_repository.get_by_id(floor.building_id)

            if building is None:
                raise ValueError("Building not found")

            return building.property_id

        if listing.space_id is not None:
            space = self.space_repository.get_by_id(listing.space_id)

            if space is None:
                raise ValueError("Space not found")

            floor = self.floor_repository.get_by_id(space.floor_id)

            if floor is None:
                raise ValueError("Floor not found")

            building = self.building_repository.get_by_id(floor.building_id)

            if building is None:
                raise ValueError("Building not found")

            return building.property_id

        raise ValueError("Listing has no valid target")
