from uuid import UUID

from sqlalchemy.orm import Session

from app.models.property_access import PropertyAccess
from app.core.property_actions import PropertyAction
from app.repositories.user_repository import UserRepository
from app.repositories.property_access_repository import (
    PropertyAccessRepository,
)
from app.repositories.property_repository import PropertyRepository


class PropertyAccessService:
    def __init__(self, db: Session):
        self.property_access_repository = PropertyAccessRepository(db)
        self.property_repository = PropertyRepository(db)
        self.user_repository = UserRepository(db)

    def grant_access(
        self,
        user_id: UUID,
        property_id: UUID,
        access_type: str,
    ) -> PropertyAccess:
        if not access_type.strip():
            raise ValueError("Access type is required")

        valid_access_types = {action.value for action in PropertyAction}
        if access_type not in valid_access_types:
            raise ValueError("Invalid property access type")

        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise ValueError("Employee not found")

        if not user.is_active:
            raise ValueError("Employee is inactive")

        if user.role != "employee":
            raise ValueError("User must be an employee")

        property = self.property_repository.get_by_id(property_id)
        if property is None:
            raise ValueError("Property not found")

        existing_access = (
            self.property_access_repository
            .get_by_user_property_type_for_update(
                user_id=user_id,
                property_id=property_id,
                access_type=access_type,
            )
        )

        if existing_access is not None:
            if existing_access.is_active:
                raise ValueError(
                    "Employee already has this property access"
                )

            existing_access.is_active = True
            self.property_access_repository.db.flush()
            return existing_access

        property_access = PropertyAccess(
            user_id=user_id,
            property_id=property_id,
            access_type=access_type,
            is_active=True,
        )

        return self.property_access_repository.add(property_access)

    def authorize(
        self,
        user_id: UUID,
        property_id: UUID,
        access_type: str,
    ) -> PropertyAccess:
        property_access = (
            self.property_access_repository.get_active_access(
                user_id=user_id,
                property_id=property_id,
                access_type=access_type,
            )
        )

        if property_access is None:
            property = self.property_repository.get_by_id(property_id)

            if property is None:
                raise ValueError("Property not found")

            raise ValueError(
                "Employee does not have access to this property"
            )

        return property_access

    def list_user_access(
        self,
        user_id: UUID,
    ) -> list[PropertyAccess]:
        return self.property_access_repository.get_by_user_id(
            user_id
        )

    def revoke_access(
        self,
        user_id: UUID,
        property_id: UUID,
        access_type: str,
    ) -> PropertyAccess:
        property_access = (
            self.property_access_repository
            .get_by_user_property_type_for_update(
                user_id=user_id,
                property_id=property_id,
                access_type=access_type,
            )
        )

        if property_access is None:
            raise ValueError(
                "Active property access not found"
            )

        return self.property_access_repository.deactivate(
            property_access
        )
