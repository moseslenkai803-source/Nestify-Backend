from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.property_installation_verification import (
    PropertyInstallationVerification,
)
from app.repositories.property_installation_repository import (
    PropertyInstallationRepository,
)
from app.repositories.installation_assignment_repository import (
    InstallationAssignmentRepository,
)
from app.repositories.property_installation_verification_repository import (
    PropertyInstallationVerificationRepository,
)
from app.repositories.user_repository import UserRepository
from app.services.address_plate_lifecycle_service import (
    AddressPlateLifecycleService,
)


class PropertyInstallationVerificationService:
    def __init__(self, db: Session):
        self.db = db
        self.property_installation_repository = (
            PropertyInstallationRepository(db)
        )
        self.property_installation_verification_repository = (
            PropertyInstallationVerificationRepository(db)
        )
        self.installation_assignment_repository = InstallationAssignmentRepository(db)
        self.user_repository = UserRepository(db)
        self.lifecycle_service = AddressPlateLifecycleService(db)

    def verify_installation(
        self,
        property_id: UUID,
        installation_id: UUID,
        verified_by: UUID,
        status: str,
        notes: str | None = None,
    ) -> PropertyInstallationVerification:
        if status not in {"verified", "rejected"}:
            raise ValueError(
                "Verification status must be 'verified' or 'rejected'"
            )

        installation = self.property_installation_repository.get_by_id(
            installation_id
        )

        if installation is None:
            raise ValueError("Installation not found")

        assignment = None
        if installation.assignment_id is not None:
            assignment = self.installation_assignment_repository.get_by_id_for_update(
                installation.assignment_id
            )

            if assignment is None:
                raise ValueError("Installation assignment not found")

            installation = self.property_installation_repository.get_by_id_for_update(
                installation_id
            )

            if installation is None:
                raise ValueError("Installation not found")

            if installation.assignment_id != assignment.id:
                raise ValueError("Installation assignment does not match installation")

            if assignment.property_id != installation.property_id:
                raise ValueError("Installation assignment does not belong to this property")

            if assignment.plate_id != installation.plate_id:
                raise ValueError("Installation assignment does not belong to this plate")

            if assignment.status == "cancelled":
                raise ValueError("Installation assignment is cancelled")

            if assignment.status != "submitted":
                raise ValueError("Installation assignment is not awaiting verification")
        else:
            installation = self.property_installation_repository.get_by_id_for_update(
                installation_id
            )

            if installation is None:
                raise ValueError("Installation not found")

        if installation.property_id != property_id:
            raise ValueError("Installation does not belong to this property")

        if installation.status != "submitted":
            raise ValueError("Installation is not awaiting verification")

        reviewer = self.user_repository.get_by_id(verified_by)

        if reviewer is None:
            raise ValueError("Verifier not found")

        if not reviewer.is_active:
            raise ValueError("Verifier is inactive")

        verification = PropertyInstallationVerification(
            installation_id=installation_id,
            verified_by=verified_by,
            status=status,
            verified_at=datetime.now(UTC),
            notes=notes,
        )

        self.property_installation_verification_repository.add(
            verification
        )

        installation.status = status

        if assignment is not None:
            if status == "verified":
                assignment.status = "completed"
            else:
                assignment.status = "in_progress"

        if status == "verified":
            self.lifecycle_service.record_event(
                plate_id=installation.plate_id,
                event_type="installed",
                performed_by=installation.installer_id,
                notes=installation.notes,
            )

            self.lifecycle_service.record_event(
                plate_id=installation.plate_id,
                event_type="verified",
                performed_by=verified_by,
                notes=notes,
            )

        self.db.flush()

        return verification
