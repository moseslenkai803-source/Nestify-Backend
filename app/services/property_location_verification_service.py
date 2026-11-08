import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.property_actions import PropertyAction
from app.models.employee_clearance import EmployeeClearance
from app.models.property_location import PropertyLocation
from app.models.property_location_verification import (
    PropertyLocationVerification,
)
from app.models.user import User
from app.repositories.employee_clearance_repository import (
    EmployeeClearanceRepository,
)
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.landlord_repository import LandlordRepository
from app.repositories.property_access_repository import (
    PropertyAccessRepository,
)
from app.repositories.property_location_repository import (
    PropertyLocationRepository,
)
from app.repositories.property_location_verification_repository import (
    PropertyLocationVerificationRepository,
)
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository


class LocationReviewError(ValueError):
    pass


class LocationReviewNotFound(LocationReviewError):
    pass


class LocationReviewAuthorizationError(LocationReviewError):
    pass


class LocationReviewConflict(LocationReviewError):
    pass


class PropertyLocationVerificationService:
    def __init__(self, db: Session):
        self.db = db
        self.property_repository = PropertyRepository(db)
        self.location_repository = PropertyLocationRepository(db)
        self.verification_repository = (
            PropertyLocationVerificationRepository(db)
        )
        self.employee_repository = EmployeeRepository(db)
        self.user_repository = UserRepository(db)
        self.clearance_repository = EmployeeClearanceRepository(db)
        self.property_access_repository = PropertyAccessRepository(db)
        self.landlord_repository = LandlordRepository(db)

    def _lock_reviewer_authorization(
        self,
        reviewer_id: uuid.UUID,
        property_id: uuid.UUID | None,
    ) -> User:
        reviewer_snapshot = self.user_repository.get_by_id(reviewer_id)
        if reviewer_snapshot is None:
            raise LocationReviewAuthorizationError(
                "Reviewer account is inactive or missing"
            )

        employee = None
        if reviewer_snapshot.role == "employee":
            employee = self.employee_repository.get_by_user_id_for_update(
                reviewer_id
            )
        reviewer = self.user_repository.get_by_id_for_update(reviewer_id)

        if reviewer is None or not reviewer.is_active:
            raise LocationReviewAuthorizationError(
                "Reviewer account is inactive or missing"
            )

        if (
            reviewer_snapshot.role == "admin"
            and reviewer.role == "admin"
        ):
            return reviewer

        if (
            reviewer_snapshot.role != "employee"
            or reviewer.role != "employee"
        ):
            raise LocationReviewAuthorizationError(
                "User is not authorized to review property locations"
            )

        if employee is None or employee.ended_at is not None:
            raise LocationReviewAuthorizationError(
                "Active employee record is required"
            )

        clearance = (
            self.clearance_repository
            .get_by_employee_and_clearance_for_update(
                employee_id=employee.id,
                clearance="property_verification",
            )
        )
        if clearance is None or not clearance.is_active:
            raise LocationReviewAuthorizationError(
                "Active property_verification clearance is required"
            )

        if property_id is not None:
            # Lock the grant so a concurrent revocation cannot race the
            # decision after authorization has been checked.
            property_access = (
                self.property_access_repository
                .get_by_user_property_type_for_update(
                    user_id=reviewer.id,
                    property_id=property_id,
                    access_type=(
                        PropertyAction.PROPERTY_VERIFICATION.value
                    ),
                )
            )
            if property_access is None or not property_access.is_active:
                raise LocationReviewAuthorizationError(
                    "Active property verification access is required"
                )

        return reviewer

    def _authorize_queue_reviewer(
        self,
        reviewer_id: uuid.UUID,
    ) -> User:
        reviewer = self.user_repository.get_by_id(reviewer_id)
        if reviewer is None or not reviewer.is_active:
            raise LocationReviewAuthorizationError(
                "Reviewer account is inactive or missing"
            )

        if reviewer.role == "admin":
            return reviewer

        if reviewer.role != "employee":
            raise LocationReviewAuthorizationError(
                "User is not authorized to review property locations"
            )

        employee = self.employee_repository.get_by_user_id(reviewer_id)
        if employee is None or employee.ended_at is not None:
            raise LocationReviewAuthorizationError(
                "Active employee record is required"
            )

        clearance = (
            self.clearance_repository.get_by_employee_and_clearance(
                employee_id=employee.id,
                clearance="property_verification",
            )
        )
        if clearance is None or not clearance.is_active:
            raise LocationReviewAuthorizationError(
                "Active property_verification clearance is required"
            )

        return reviewer

    def _authorize_history(
        self,
        property_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> User:
        property_record = self.property_repository.get_by_id(property_id)
        if property_record is None:
            raise LocationReviewNotFound("Property not found")

        user_snapshot = self.user_repository.get_by_id(user_id)
        if user_snapshot is None:
            raise LocationReviewAuthorizationError(
                "User account is inactive or missing"
            )
        employee = None
        if user_snapshot.role == "employee":
            employee = self.employee_repository.get_by_user_id(user_id)
        user = self.user_repository.get_by_id(user_id)
        if user is None or not user.is_active:
            raise LocationReviewAuthorizationError(
                "User account is inactive or missing"
            )

        if user_snapshot.role == "admin" and user.role == "admin":
            return user

        landlord = self.landlord_repository.get_by_user_id(user_id)
        if landlord is not None and landlord.id == property_record.landlord_id:
            return user

        if (
            user_snapshot.role != "employee"
            or user.role != "employee"
            or employee is None
        ):
            raise LocationReviewAuthorizationError(
                "User is not authorized to view property location history"
            )
        if employee.ended_at is not None:
            raise LocationReviewAuthorizationError(
                "Employee is terminated"
            )
        clearance = (
            self.clearance_repository.get_by_employee_and_clearance(
                employee_id=employee.id,
                clearance="property_verification",
            )
        )
        if clearance is not None and clearance.is_active:
            verification_access = (
                self.property_access_repository.get_active_access(
                    user_id=user_id,
                    property_id=property_id,
                    access_type=(
                        PropertyAction.PROPERTY_VERIFICATION.value
                    ),
                )
            )
            if verification_access is not None:
                return user

        management_access = (
            self.property_access_repository.get_active_access(
                user_id=user_id,
                property_id=property_id,
                access_type=PropertyAction.PROPERTY_MANAGEMENT.value,
            )
        )
        if management_access is not None:
            return user

        raise LocationReviewAuthorizationError(
            "User is not authorized to view property location history"
        )

    @staticmethod
    def _history_state(location: PropertyLocation) -> str:
        if location.status == "unverified":
            return "legacy"
        if location.status == "pending":
            return "pending"
        if location.status == "rejected":
            return "rejected"
        if location.is_current:
            return "current"
        return "superseded"

    @classmethod
    def _history_item(
        cls,
        location: PropertyLocation,
        verification: PropertyLocationVerification | None,
    ) -> dict[str, object]:
        return {
            "id": location.id,
            "property_id": location.property_id,
            "version_number": location.version_number,
            "submitted_by_id": location.submitted_by_id,
            "submitted_at": location.submitted_at,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "source": location.source,
            "capture_method": location.capture_method,
            "accuracy_meters": location.accuracy_meters,
            "captured_at": location.captured_at,
            "status": location.status,
            "is_current": location.is_current,
            "history_state": cls._history_state(location),
            "verification": verification,
        }

    def get_current_location(
        self,
        property_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PropertyLocation:
        self._authorize_history(property_id, user_id)
        location = (
            self.location_repository.get_current_verified_location_by_property_id(
                property_id
            )
        )
        if location is None:
            raise LocationReviewNotFound(
                "Current approved property location not found"
            )
        return location

    def get_location_history(
        self,
        property_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[dict[str, object]]:
        self._authorize_history(property_id, user_id)
        return [
            self._history_item(location, verification)
            for location, verification
            in self.location_repository.get_history_by_property_id(
                property_id
            )
        ]

    def list_pending_reviews(
        self,
        reviewer_id: uuid.UUID,
    ) -> list[dict[str, object]]:
        reviewer = self._authorize_queue_reviewer(reviewer_id)
        if reviewer.role == "admin":
            locations = self.location_repository.get_all_pending()
        else:
            locations = self.location_repository.get_pending_for_reviewer(
                user_id=reviewer.id,
                clearance="property_verification",
                access_type=PropertyAction.PROPERTY_VERIFICATION.value,
            )
        return [
            self._history_item(location, None)
            for location in locations
        ]

    def approve_location(
        self,
        property_id: uuid.UUID,
        location_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        verification_method: str,
        notes: str | None = None,
    ) -> PropertyLocationVerification:
        return self._decide_location(
            property_id=property_id,
            location_id=location_id,
            reviewer_id=reviewer_id,
            decision="approved",
            verification_method=verification_method,
            notes=notes,
        )

    def reject_location(
        self,
        property_id: uuid.UUID,
        location_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        verification_method: str,
        notes: str | None = None,
    ) -> PropertyLocationVerification:
        return self._decide_location(
            property_id=property_id,
            location_id=location_id,
            reviewer_id=reviewer_id,
            decision="rejected",
            verification_method=verification_method,
            notes=notes,
        )

    def _decide_location(
        self,
        property_id: uuid.UUID,
        location_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        decision: Literal["approved", "rejected"],
        verification_method: str,
        notes: str | None,
    ) -> PropertyLocationVerification:
        if not verification_method.strip():
            raise ValueError("Verification method is required")
        if len(verification_method) > 100:
            raise ValueError("Verification method must not exceed 100 characters")

        property_record = self.property_repository.get_by_id_for_update(
            property_id
        )
        if property_record is None:
            raise LocationReviewNotFound("Property not found")

        # The property lock serializes decisions across location versions,
        # including replacement of the single current location.
        location = self.location_repository.get_by_property_and_id_for_update(
            property_id=property_id,
            location_id=location_id,
        )
        if location is None:
            raise LocationReviewNotFound(
                "Property location version not found"
            )

        current_location = None
        if decision == "approved":
            current_location = (
                self.location_repository.get_current_by_property_id_for_update(
                    property_id
                )
            )

        reviewer = self._lock_reviewer_authorization(
            reviewer_id=reviewer_id,
            property_id=property_id,
        )
        if location.submitted_by_id == reviewer.id:
            raise LocationReviewAuthorizationError(
                "Submitters cannot review their own location"
            )

        existing_decision = (
            self.verification_repository.get_by_location_id(location.id)
        )
        if existing_decision is not None or location.status != "pending":
            raise LocationReviewConflict(
                "Property location version has already been decided or is not pending"
            )

        verification = PropertyLocationVerification(
            location_id=location.id,
            verified_by=reviewer.id,
            decision=decision,
            verification_method=verification_method.strip(),
            verified_at=datetime.now(UTC),
            notes=notes,
        )

        try:
            with self.db.begin_nested():
                if decision == "approved":
                    if current_location is not None:
                        current_location.is_current = False
                        self.db.flush()
                    location.status = "approved"
                    location.is_current = True
                else:
                    location.status = "rejected"

                return self.verification_repository.add(verification)
        except IntegrityError as exc:
            constraint_name = getattr(
                getattr(exc.orig, "diag", None),
                "constraint_name",
                None,
            )
            if constraint_name in {
                "uq_property_location_verifications_location",
                "uq_property_locations_one_current_per_property",
            }:
                raise LocationReviewConflict(
                    "Property location decision conflicts with an existing decision; retry"
                ) from exc
            raise
