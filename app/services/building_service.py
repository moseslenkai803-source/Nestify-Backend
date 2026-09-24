import uuid

from sqlalchemy.orm import Session

from app.core.property_actions import PropertyAction
from app.models.building import Building
from app.models.user import User
from app.repositories.building_repository import BuildingRepository
from app.services.property_authorization_service import (
    PropertyAuthorizationService,
)


class BuildingService:
    def __init__(self, db: Session):
        self.building_repository = BuildingRepository(db)
        self.property_authorization_service = PropertyAuthorizationService(db)

    def create_building(
        self,
        user: User,
        property_id: uuid.UUID,
        building_number: str,
        name: str | None = None,
    ) -> Building:
        self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        building = Building(
            property_id=property_id,
            building_number=building_number,
            name=name,
            status="draft",
        )

        return self.building_repository.add(building)

    def get_building(
        self,
        building_id: uuid.UUID,
    ) -> Building:
        building = self.building_repository.get_by_id(building_id)

        if building is None:
            raise ValueError("Building not found")

        return building

    def list_buildings(
        self,
        user: User,
        property_id: uuid.UUID,
    ) -> list[Building]:
        self.property_authorization_service.authorize(
            user=user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        return self.building_repository.get_by_property_id(property_id)
