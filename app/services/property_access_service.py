from uuid import UUID

from sqlalchemy.orm import Session

from app.models.property_access import PropertyAccess
from app.repositories.property_access_repository import (
    PropertyAccessRepository,
)


class PropertyAccessService:
    def __init__(self, db: Session):
        self.property_access_repository = PropertyAccessRepository(db)

    def grant_access(
        self,
        user_id: UUID,
        property_id: UUID,
        access_type: str,
    ) -> PropertyAccess:
        if not access_type.strip():
            raise ValueError("Access type is required")

        existing_access = (
            self.property_access_repository.get_active_access(
                user_id=user_id,
                property_id=property_id,
                access_type=access_type,
            )
        )

        if existing_access is not None:
            raise ValueError(
                "Employee already has this property access"
            )

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
            self.property_access_repository.get_active_access(
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
