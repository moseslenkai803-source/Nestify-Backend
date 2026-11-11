from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.property_installation import PropertyInstallation
from app.models.user import User
from app.models.property_installation_verification import (
    PropertyInstallationVerification,
)
from app.core.property_actions import PropertyAction
from app.repositories.property_access_repository import PropertyAccessRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.employee_clearance_repository import (
    EmployeeClearanceRepository,
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
        self.property_access_repository = PropertyAccessRepository(db)
        self.employee_repository = EmployeeRepository(db)
        self.employee_clearance_repository = EmployeeClearanceRepository(db)
        self.property_installation_repository = (
            PropertyInstallationRepository(db)
        )
        self.property_installation_verification_repository = (
            PropertyInstallationVerificationRepository(db)
        )
        self.installation_assignment_repository = InstallationAssignmentRepository(db)
        self.user_repository = UserRepository(db)
        self.lifecycle_service = AddressPlateLifecycleService(db)


    def _authorize_reviewer(
        self,
        user: User,
        property_id: UUID | None = None,
    ) -> None:
        if user.role == "admin":
            locked_user = self.user_repository.get_by_id_for_update(
                user.id
            )

            if (
                locked_user is None
                or not locked_user.is_active
                or locked_user.role != "admin"
            ):
                raise ValueError(
                    "User is not authorized to verify installations"
                )
            return

        if user.role != "employee":
            raise ValueError(
                "User is not authorized to verify installations"
            )

        employee = self.employee_repository.get_by_user_id_for_update(
            user.id
        )

        if employee is None or employee.ended_at is not None:
            raise ValueError(
                "User is not authorized to verify installations"
            )

        locked_user = self.user_repository.get_by_id_for_update(
            employee.user_id
        )

        if (
            locked_user is None
            or not locked_user.is_active
            or locked_user.role != "employee"
        ):
            raise ValueError(
                "User is not authorized to verify installations"
            )

        clearance = (
            self.employee_clearance_repository
            .get_by_employee_and_clearance(
                employee_id=employee.id,
                clearance="installation_verification",
            )
        )

        if clearance is None:
            raise ValueError(
                "User is not authorized to verify installations"
            )

        clearance = (
            self.employee_clearance_repository.get_by_id_for_update(
                clearance.id
            )
        )

        if clearance is None or not clearance.is_active:
            raise ValueError(
                "User is not authorized to verify installations"
            )

        if property_id is not None:
            property_access = (
                self.property_access_repository
                .get_by_user_property_type_for_update(
                    user_id=user.id,
                    property_id=property_id,
                    access_type=(
                        PropertyAction.INSTALLATION_VERIFICATION.value
                    ),
                )
            )

            if property_access is None or not property_access.is_active:
                raise ValueError(
                    "User is not authorized to verify installations"
                )

    def list_pending_installations(
        self,
        user: User,
    ) -> list[PropertyInstallation]:
        self._authorize_reviewer(user)

        if user.role == "admin":
            return self.property_installation_repository.get_all_submitted()

        properties = (
            self.property_access_repository
            .get_active_properties_by_user_id_and_access_type(
                user_id=user.id,
                access_type=PropertyAction.INSTALLATION_VERIFICATION.value,
            )
        )

        property_ids = [property.id for property in properties]

        return self.property_installation_repository.get_submitted_by_property_ids(
            property_ids
        )

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
            # Lock assignment before installation so cancellation/submission
            # races cannot verify stale assignment state.
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

            if assignment.status not in {"submitted", "cancelled"}:
                raise ValueError(
                    "Installation assignment is not awaiting verification"
                )
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

        self._authorize_reviewer(
            reviewer,
            property_id=installation.property_id,
        )

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

        if assignment is not None and assignment.status != "cancelled":
            if status == "verified":
                assignment.status = "completed"
            else:
                assignment.status = "in_progress"

        if status == "verified":
            # Persist the installation decision and both lifecycle transitions
            # in one transaction so activation cannot observe partial evidence.
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
