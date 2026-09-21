from uuid import UUID

from sqlalchemy.orm import Session

from app.core.property_actions import PropertyAction
from app.models.property import Property
from app.models.user import User
from app.repositories.landlord_repository import LandlordRepository
from app.repositories.property_access_repository import PropertyAccessRepository
from app.repositories.property_repository import PropertyRepository


class PropertyAuthorizationService:
    def __init__(self, db: Session):
        self.property_repository = PropertyRepository(db)
        self.landlord_repository = LandlordRepository(db)
        self.property_access_repository = PropertyAccessRepository(db)

    def authorize(
        self,
        user: User,
        property_id: UUID,
        action: PropertyAction,
    ) -> Property:
        if not user.is_active:
            raise ValueError("User account is inactive")

        if not isinstance(action, PropertyAction):
            raise ValueError("Invalid property action")

        property = self.property_repository.get_by_id(property_id)

        if property is None:
            raise ValueError("Property not found")

        landlord = self.landlord_repository.get_by_id(property.landlord_id)

        if landlord is not None and landlord.user_id == user.id:
            return property

        access = self.property_access_repository.get_active_access(
            user_id=user.id,
            property_id=property.id,
            access_type=action.value,
        )

        if access is not None:
            return property

        raise ValueError("User is not authorized for this property")
