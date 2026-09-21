from uuid import UUID

from sqlalchemy.orm import Session

from app.models.property_access import PropertyAccess


class PropertyAccessRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        property_access: PropertyAccess,
    ) -> PropertyAccess:
        self.db.add(property_access)
        self.db.flush()

        return property_access

    def get_active_access(
        self,
        user_id: UUID,
        property_id: UUID,
        access_type: str,
    ) -> PropertyAccess | None:
        return (
            self.db.query(PropertyAccess)
            .filter(
                PropertyAccess.user_id == user_id,
                PropertyAccess.property_id == property_id,
                PropertyAccess.access_type == access_type,
                PropertyAccess.is_active.is_(True),
            )
            .first()
        )

    def get_by_user_id(
        self,
        user_id: UUID,
    ) -> list[PropertyAccess]:
        return (
            self.db.query(PropertyAccess)
            .filter(PropertyAccess.user_id == user_id)
            .order_by(PropertyAccess.created_at.desc())
            .all()
        )

    def deactivate(
        self,
        property_access: PropertyAccess,
    ) -> PropertyAccess:
        property_access.is_active = False
        self.db.flush()

        return property_access
