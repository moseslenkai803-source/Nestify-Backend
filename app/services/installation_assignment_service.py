from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.installation_assignment import InstallationAssignment
from app.models.property_installation import PropertyInstallation
from app.repositories.address_plate_repository import AddressPlateRepository
from app.repositories.contractor_member_repository import ContractorMemberRepository
from app.repositories.contractor_repository import ContractorRepository
from app.repositories.installation_assignment_repository import (
    InstallationAssignmentRepository,
)
from app.repositories.property_installation_repository import PropertyInstallationRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository
from app.services.address_plate_lifecycle_service import AddressPlateLifecycleService


class InstallationAssignmentService:
    def __init__(self, db: Session):
        self.db = db
        self.property_repository = PropertyRepository(db)
        self.address_plate_repository = AddressPlateRepository(db)
        self.contractor_repository = ContractorRepository(db)
        self.contractor_member_repository = ContractorMemberRepository(db)
        self.installation_assignment_repository = (
            InstallationAssignmentRepository(db)
        )
        self.property_installation_repository = PropertyInstallationRepository(db)
        self.user_repository = UserRepository(db)
        self.lifecycle_service = AddressPlateLifecycleService(db)

    def _require_plate_dispatched(self, plate_id: UUID) -> None:
        latest_event = self.lifecycle_service.get_latest_event(plate_id)

        if latest_event is None or latest_event.event_type != "dispatched":
            raise ValueError(
                "Address plate must be dispatched before installation"
            )

    def create_assignment(
        self,
        property_id: UUID,
        plate_id: UUID,
        contractor_id: UUID,
        contractor_member_id: UUID,
        assigned_by: UUID,
        due_at: datetime | None = None,
    ) -> InstallationAssignment:
        property = self.property_repository.get_by_id_for_update(property_id)

        if property is None:
            raise ValueError("Property not found")

        plate = self.address_plate_repository.get_by_id_for_update(plate_id)

        if plate is None:
            raise ValueError("Address plate not found")

        if plate.property_id != property_id:
            raise ValueError("Address plate is not linked to this property")

        contractor = self.contractor_repository.get_by_id_for_update(
            contractor_id
        )

        if contractor is None:
            raise ValueError("Contractor not found")

        if contractor.status != "active":
            raise ValueError("Contractor is inactive")

        contractor_member = (
            self.contractor_member_repository.get_by_id_for_update(
                contractor_member_id
            )
        )

        if contractor_member is None:
            raise ValueError("Contractor member not found")

        if contractor_member.contractor_id != contractor_id:
            raise ValueError("Contractor member does not belong to this contractor")

        if not contractor_member.is_active:
            raise ValueError("Contractor member is inactive")

        contractor_member_user = self.user_repository.get_by_id(
            contractor_member.user_id
        )

        if contractor_member_user is None:
            raise ValueError("Contractor member user not found")

        if not contractor_member_user.is_active:
            raise ValueError("Contractor member user is inactive")

        assigned_user = self.user_repository.get_by_id(assigned_by)

        if assigned_user is None:
            raise ValueError("Assigning employee not found")

        if not assigned_user.is_active:
            raise ValueError("Assigning employee is inactive")

        if assigned_user.role not in {"admin", "employee"}:
            raise ValueError("Only Nestify employees can assign installations")

        existing_property_assignment = (
            self.installation_assignment_repository.get_active_by_property_id(
                property_id
            )
        )

        if existing_property_assignment is not None:
            raise ValueError(
                "Property already has an active installation assignment"
            )

        existing_plate_assignment = (
            self.installation_assignment_repository.get_active_by_plate_id(
                plate_id
            )
        )

        if existing_plate_assignment is not None:
            raise ValueError(
                "Address plate already has an active installation assignment"
            )

        assignment = InstallationAssignment(
            property_id=property_id,
            plate_id=plate_id,
            contractor_id=contractor_id,
            contractor_member_id=contractor_member_id,
            assigned_by=assigned_by,
            due_at=due_at,
            status="assigned",
        )

        self.installation_assignment_repository.add(assignment)

        return assignment

    def start_assignment(
        self,
        assignment_id: UUID,
        contractor_user_id: UUID,
    ) -> InstallationAssignment:
        assignment = self.installation_assignment_repository.get_by_id_for_update(
            assignment_id
        )

        if assignment is None:
            raise ValueError("Installation assignment not found")

        if assignment.status != "assigned":
            raise ValueError("Installation assignment is not awaiting start")

        contractor_member = (
            self.contractor_member_repository.get_by_id_for_update(
                assignment.contractor_member_id
            )
        )

        if contractor_member is None:
            raise ValueError("Contractor member not found")

        if contractor_member.user_id != contractor_user_id:
            raise ValueError(
                "Contractor user is not assigned to this installation"
            )

        if not contractor_member.is_active:
            raise ValueError("Contractor member is inactive")

        contractor_member_user = self.user_repository.get_by_id(
            contractor_member.user_id
        )

        if contractor_member_user is None:
            raise ValueError("Contractor member user not found")

        if not contractor_member_user.is_active:
            raise ValueError("Contractor member user is inactive")

        if contractor_member_user.role != "contractor":
            raise ValueError("Contractor member user must be a contractor")

        self._require_plate_dispatched(assignment.plate_id)

        assignment.status = "in_progress"
        self.db.flush()

        return assignment

    def cancel_assignment(
        self,
        assignment_id: UUID,
        cancelled_by: UUID,
        reason: str,
    ) -> InstallationAssignment:
        assignment = self.installation_assignment_repository.get_by_id_for_update(
            assignment_id
        )

        if assignment is None:
            raise ValueError("Installation assignment not found")

        if assignment.status not in {"assigned", "in_progress", "submitted"}:
            raise ValueError("Installation assignment cannot be cancelled")

        employee = self.user_repository.get_by_id(cancelled_by)

        if employee is None:
            raise ValueError("Cancelling employee not found")

        if not employee.is_active:
            raise ValueError("Cancelling employee is inactive")

        if employee.role not in {"admin", "employee"}:
            raise ValueError("Only Nestify employees can cancel installations")

        if not reason.strip():
            raise ValueError("Cancellation reason is required")

        assignment.status = "cancelled"
        assignment.cancelled_by = cancelled_by
        assignment.cancelled_at = datetime.now(UTC)
        assignment.cancellation_reason = reason.strip()

        self.db.flush()

        return assignment

    def submit_assignment(
        self,
        assignment_id: UUID,
        contractor_user_id: UUID,
        latitude: float,
        longitude: float,
        accuracy_meters: float | None,
        captured_at: datetime,
        notes: str | None = None,
    ) -> PropertyInstallation:
        assignment = self.installation_assignment_repository.get_by_id_for_update(
            assignment_id
        )

        if assignment is None:
            raise ValueError("Installation assignment not found")

        if assignment.status != "in_progress":
            raise ValueError(
                "Installation assignment is not in progress"
            )

        contractor_member = (
            self.contractor_member_repository.get_by_id_for_update(
                assignment.contractor_member_id
            )
        )

        if contractor_member is None:
            raise ValueError("Contractor member not found")

        if contractor_member.user_id != contractor_user_id:
            raise ValueError(
                "Contractor user is not assigned to this installation"
            )

        if not contractor_member.is_active:
            raise ValueError("Contractor member is inactive")

        contractor_member_user = self.user_repository.get_by_id(
            contractor_member.user_id
        )

        if contractor_member_user is None:
            raise ValueError("Contractor member user not found")

        if not contractor_member_user.is_active:
            raise ValueError("Contractor member user is inactive")

        if contractor_member_user.role != "contractor":
            raise ValueError("Contractor member user must be a contractor")

        self._require_plate_dispatched(assignment.plate_id)

        if not -90 <= latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90")

        if not -180 <= longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180")

        if accuracy_meters is not None and accuracy_meters < 0:
            raise ValueError(
                "Accuracy must be greater than or equal to 0"
            )

        if captured_at.tzinfo is None:
            raise ValueError("Captured timestamp must be timezone-aware")

        existing_installation = (
            self.property_installation_repository.get_by_assignment_id_for_update(
                assignment_id
            )
        )

        if existing_installation is not None and existing_installation.status == "submitted":
            raise ValueError(
                "Installation assignment already has a submitted installation"
            )

        installation = PropertyInstallation(
            property_id=assignment.property_id,
            plate_id=assignment.plate_id,
            assignment_id=assignment.id,
            installer_id=contractor_member.user_id,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            captured_at=captured_at,
            status="submitted",
            notes=notes,
        )

        self.property_installation_repository.add(installation)
        assignment.status = "submitted"
        self.db.flush()

        return installation
