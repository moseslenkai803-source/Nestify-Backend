import math
import uuid
from datetime import UTC, datetime

from geoalchemy2.elements import WKTElement
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.property_actions import PropertyAction
from app.models.property import Property
from app.models.property_location import PropertyLocation
from app.models.user import User
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.landlord_repository import LandlordRepository
from app.repositories.property_access_repository import (
    PropertyAccessRepository,
)
from app.repositories.property_location_repository import (
    PropertyLocationRepository,
)
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository


class LocationSubmissionConflict(ValueError):
    pass


class PropertyLocationService:
    def __init__(self, db: Session):
        self.db = db
        self.property_repository = PropertyRepository(db)
        self.property_location_repository = PropertyLocationRepository(db)
        self.employee_repository = EmployeeRepository(db)
        self.user_repository = UserRepository(db)
        self.landlord_repository = LandlordRepository(db)
        self.property_access_repository = PropertyAccessRepository(db)

    def _authorize_submitter(
        self,
        property_record: Property,
        user_id: uuid.UUID,
    ) -> User:
        employee = self.employee_repository.get_by_user_id_for_update(user_id)
        user = self.user_repository.get_by_id_for_update(user_id)

        if user is None or not user.is_active:
            raise ValueError("User account is inactive")

        if user.role == "admin":
            return user

        landlord = self.landlord_repository.get_by_user_id(user_id)
        if landlord is not None:
            if landlord.id == property_record.landlord_id:
                return user

        if user.role != "employee":
            raise ValueError("User is not authorized for this property")

        if employee is None or employee.ended_at is not None:
            raise ValueError("Employee is terminated")

        access = self.property_access_repository.get_by_user_property_type_for_update(
            user_id=user_id,
            property_id=property_record.id,
            access_type=PropertyAction.PROPERTY_MANAGEMENT.value,
        )
        if access is None or not access.is_active:
            raise ValueError("User is not authorized for this property")

        return user

    def get_location(
        self,
        property_id: uuid.UUID,
    ) -> PropertyLocation:
        location = (
            self.property_location_repository.get_current_verified_location_by_property_id(
                property_id
            )
        )

        if location is None:
            raise ValueError("Current approved property location not found")

        return location

    def create_location(
        self,
        property_id: uuid.UUID,
        submitted_by_id: uuid.UUID,
        latitude: float,
        longitude: float,
        source: str,
        capture_method: str,
        captured_at: datetime,
        accuracy_meters: float | None = None,
    ) -> PropertyLocation:
        # Serializing on the property row protects both pending-location
        # admission and the next version number from concurrent submissions.
        property = self.property_repository.get_by_id_for_update(property_id)

        if property is None:
            raise ValueError("Property not found")

        self._authorize_submitter(property, submitted_by_id)

        pending_location = (
            self.property_location_repository.get_pending_by_property_id(
                property_id
            )
        )
        if pending_location is not None:
            raise LocationSubmissionConflict(
                "Property already has a pending location"
            )

        current_max_version = (
            self.property_location_repository.get_max_version_number(
                property_id
            )
        )
        version_number = (
            1 if current_max_version is None else current_max_version + 1
        )

        if not math.isfinite(latitude) or not -90 <= latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90")

        if not math.isfinite(longitude) or not -180 <= longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180")

        if accuracy_meters is not None and (
            not math.isfinite(accuracy_meters) or accuracy_meters < 0
        ):
            raise ValueError("Accuracy must be greater than or equal to 0")

        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            raise ValueError("Captured at timestamp must be timezone-aware")

        location = WKTElement(
            f"POINT({longitude} {latitude})",
            srid=4326,
        )

        property_location = PropertyLocation(
            property_id=property_id,
            version_number=version_number,
            submitted_by_id=submitted_by_id,
            submitted_at=datetime.now(UTC),
            is_current=False,
            latitude=latitude,
            longitude=longitude,
            location=location,
            source=source,
            capture_method=capture_method,
            accuracy_meters=accuracy_meters,
            captured_at=captured_at,
            status="pending",
        )

        try:
            with self.db.begin_nested():
                return self.property_location_repository.add(property_location)
        except IntegrityError as exc:
            constraint_name = getattr(
                getattr(exc.orig, "diag", None),
                "constraint_name",
                None,
            )
            if (
                constraint_name
                == "uq_property_locations_one_pending_per_property"
            ):
                raise LocationSubmissionConflict(
                    "Property already has a pending location"
                ) from exc
            if constraint_name == "uq_property_locations_property_version":
                raise LocationSubmissionConflict(
                    "Property location version conflict; retry submission"
                ) from exc
            raise
