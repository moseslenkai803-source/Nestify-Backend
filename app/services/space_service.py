import uuid

from sqlalchemy.orm import Session

from app.core.property_actions import PropertyAction
from app.models.space import Space
from app.models.user import User
from app.repositories.building_repository import BuildingRepository
from app.repositories.floor_repository import FloorRepository
from app.repositories.space_repository import SpaceRepository
from app.services.property_authorization_service import (
    PropertyAuthorizationService,
)


class SpaceService:
    def __init__(self, db: Session):
        self.space_repository = SpaceRepository(db)
        self.floor_repository = FloorRepository(db)
        self.building_repository = BuildingRepository(db)
        self.property_authorization_service = PropertyAuthorizationService(db)

    def create_space(
        self,
        user: User,
        property_id: uuid.UUID,
        building_id: uuid.UUID,
        floor_id: uuid.UUID,
        space_number: str,
        name: str | None = None,
        space_type: str = "general",
    ) -> Space:
        building = self.building_repository.get_by_id(building_id)

        if building is None:
            raise ValueError("Building not found")

        if building.property_id != property_id:
            raise ValueError("Building not found")

        floor = self.floor_repository.get_by_id(floor_id)

        if floor is None:
            raise ValueError("Floor not found")

        if floor.building_id != building_id:
            raise ValueError("Floor not found")

        self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        space = Space(
            floor_id=floor_id,
            space_number=space_number,
            name=name,
            space_type=space_type,
            status="draft",
        )

        return self.space_repository.add(space)

    def get_space(
        self,
        user: User,
        property_id: uuid.UUID,
        building_id: uuid.UUID,
        floor_id: uuid.UUID,
        space_id: uuid.UUID,
    ) -> Space:
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

        return space

    def list_spaces(
        self,
        user: User,
        property_id: uuid.UUID,
        building_id: uuid.UUID,
        floor_id: uuid.UUID,
    ) -> list[Space]:
        building = self.building_repository.get_by_id(building_id)

        if building is None:
            raise ValueError("Building not found")

        if building.property_id != property_id:
            raise ValueError("Building not found")

        floor = self.floor_repository.get_by_id(floor_id)

        if floor is None:
            raise ValueError("Floor not found")

        if floor.building_id != building_id:
            raise ValueError("Floor not found")

        self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        return self.space_repository.get_by_floor_id(floor_id)
