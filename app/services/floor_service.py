import uuid

from sqlalchemy.orm import Session

from app.core.property_actions import PropertyAction
from app.models.floor import Floor
from app.models.user import User
from app.repositories.building_repository import BuildingRepository
from app.repositories.floor_repository import FloorRepository
from app.services.property_authorization_service import (
    PropertyAuthorizationService,
)


class FloorService:
    def __init__(self, db: Session):
        self.floor_repository = FloorRepository(db)
        self.building_repository = BuildingRepository(db)
        self.property_authorization_service = PropertyAuthorizationService(db)

    def create_floor(
        self,
        user: User,
        property_id: uuid.UUID,
        building_id: uuid.UUID,
        floor_number: str,
        name: str | None = None,
    ) -> Floor:
        building = self.building_repository.get_by_id(building_id)

        if building is None:
            raise ValueError("Building not found")

        if building.property_id != property_id:
            raise ValueError("Building not found")

        self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        floor = Floor(
            building_id=building_id,
            floor_number=floor_number,
            name=name,
            status="draft",
        )

        return self.floor_repository.add(floor)

    def get_floor(
        self,
        user: User,
        property_id: uuid.UUID,
        floor_id: uuid.UUID,
    ) -> Floor:
        floor = self.floor_repository.get_by_id(floor_id)

        if floor is None:
            raise ValueError("Floor not found")

        building = self.building_repository.get_by_id(floor.building_id)

        if building is None:
            raise ValueError("Building not found")

        if building.property_id != property_id:
            raise ValueError("Floor not found")

        self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        return floor

    def list_floors(
        self,
        user: User,
        property_id: uuid.UUID,
        building_id: uuid.UUID,
    ) -> list[Floor]:
        building = self.building_repository.get_by_id(building_id)

        if building is None:
            raise ValueError("Building not found")

        if building.property_id != property_id:
            raise ValueError("Building not found")

        self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        return self.floor_repository.get_by_building_id(building_id)
