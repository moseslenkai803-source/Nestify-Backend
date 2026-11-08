from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_clearance import EmployeeClearance
from app.models.property_access import PropertyAccess
from app.models.property_location import PropertyLocation
from app.models.property_location_verification import (
    PropertyLocationVerification,
)
from app.models.user import User


class PropertyLocationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, property_location: PropertyLocation) -> PropertyLocation:
        self.db.add(property_location)
        self.db.flush()
        return property_location

    def get_by_id(self, location_id: UUID) -> PropertyLocation | None:
        return self.db.get(PropertyLocation, location_id)

    def get_by_property_and_id_for_update(
        self,
        property_id: UUID,
        location_id: UUID,
    ) -> PropertyLocation | None:
        statement = (
            select(PropertyLocation)
            .where(
                PropertyLocation.property_id == property_id,
                PropertyLocation.id == location_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.db.scalar(statement)

    def get_current_verified_location_by_property_id(
        self,
        property_id: UUID,
    ) -> PropertyLocation | None:
        """Require both current approval state and its linked decision evidence."""
        statement = (
            select(PropertyLocation)
            .join(
                PropertyLocationVerification,
                PropertyLocationVerification.location_id
                == PropertyLocation.id,
            )
            .where(
                PropertyLocation.property_id == property_id,
                PropertyLocation.status == "approved",
                PropertyLocation.is_current.is_(True),
                PropertyLocationVerification.decision == "approved",
            )
        )
        return self.db.scalar(statement)

    def get_current_by_property_id_for_update(
        self,
        property_id: UUID,
    ) -> PropertyLocation | None:
        statement = (
            select(PropertyLocation)
            .where(
                PropertyLocation.property_id == property_id,
                PropertyLocation.is_current.is_(True),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.db.scalar(statement)

    def get_history_by_property_id(
        self,
        property_id: UUID,
    ) -> list[tuple[PropertyLocation, PropertyLocationVerification | None]]:
        statement = (
            select(PropertyLocation, PropertyLocationVerification)
            .outerjoin(
                PropertyLocationVerification,
                PropertyLocationVerification.location_id
                == PropertyLocation.id,
            )
            .where(PropertyLocation.property_id == property_id)
            .order_by(
                PropertyLocation.version_number.desc(),
                PropertyLocation.id.desc(),
            )
        )
        return list(self.db.execute(statement).all())

    def get_pending_by_property_ids(
        self,
        property_ids: list[UUID],
    ) -> list[PropertyLocation]:
        if not property_ids:
            return []

        statement = (
            select(PropertyLocation)
            .where(
                PropertyLocation.property_id.in_(property_ids),
                PropertyLocation.status == "pending",
            )
            .order_by(
                PropertyLocation.created_at.asc(),
                PropertyLocation.id.asc(),
            )
        )
        return list(self.db.scalars(statement).all())

    def get_all_pending(self) -> list[PropertyLocation]:
        statement = (
            select(PropertyLocation)
            .where(PropertyLocation.status == "pending")
            .order_by(
                PropertyLocation.created_at.asc(),
                PropertyLocation.id.asc(),
            )
        )
        return list(self.db.scalars(statement).all())

    def get_pending_for_reviewer(
        self,
        user_id: UUID,
        clearance: str,
        access_type: str,
    ) -> list[PropertyLocation]:
        statement = (
            select(PropertyLocation)
            .join(
                PropertyAccess,
                PropertyAccess.property_id == PropertyLocation.property_id,
            )
            .join(
                Employee,
                Employee.user_id == PropertyAccess.user_id,
            )
            .join(User, User.id == Employee.user_id)
            .join(
                EmployeeClearance,
                EmployeeClearance.employee_id == Employee.id,
            )
            .where(
                PropertyLocation.status == "pending",
                PropertyAccess.user_id == user_id,
                PropertyAccess.access_type == access_type,
                PropertyAccess.is_active.is_(True),
                Employee.ended_at.is_(None),
                EmployeeClearance.clearance == clearance,
                EmployeeClearance.is_active.is_(True),
                User.role == "employee",
                User.is_active.is_(True),
            )
            .order_by(
                PropertyLocation.created_at.asc(),
                PropertyLocation.id.asc(),
            )
        )
        return list(self.db.scalars(statement).all())

    def get_pending_by_property_id(
        self,
        property_id: UUID,
    ) -> PropertyLocation | None:
        statement = (
            select(PropertyLocation)
            .where(
                PropertyLocation.property_id == property_id,
                PropertyLocation.status == "pending",
            )
        )
        return self.db.scalar(statement)

    def get_max_version_number(
        self,
        property_id: UUID,
    ) -> int | None:
        statement = select(func.max(PropertyLocation.version_number)).where(
            PropertyLocation.property_id == property_id
        )
        return self.db.scalar(statement)
