from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.address_plate_repository import (
    AddressPlateRepository,
)
from app.repositories.installation_assignment_repository import (
    InstallationAssignmentRepository,
)


class InstallationAssignmentQueryService:
    def __init__(self, db: Session):
        self.installation_assignment_repository = (
            InstallationAssignmentRepository(db)
        )
        self.address_plate_repository = AddressPlateRepository(db)

    def list_dispatched_plates(
        self,
        property_id: UUID,
    ) -> list[dict]:
        plates = (
            self.address_plate_repository
            .get_dispatched_by_property_id(property_id)
        )

        return [
            {
                "id": plate.id,
                "plate_code": plate.plate_code,
                "property_id": plate.property_id,
            }
            for plate in plates
        ]

    def get_assignment(
        self,
        assignment_id: UUID,
    ) -> dict | None:
        record = (
            self.installation_assignment_repository
            .get_enriched_record_by_id(assignment_id)
        )

        if record is None:
            return None

        (
            assignment,
            property_name,
            plate_code,
            contractor_name,
            installer_email,
            assigned_by_email,
        ) = record

        return {
            "id": assignment.id,
            "property_id": assignment.property_id,
            "property_name": property_name,
            "plate_id": assignment.plate_id,
            "plate_code": plate_code,
            "contractor_id": assignment.contractor_id,
            "contractor_name": contractor_name,
            "contractor_member_id": assignment.contractor_member_id,
            "installer_email": installer_email,
            "assigned_by": assignment.assigned_by,
            "assigned_by_email": assigned_by_email,
            "assigned_at": assignment.assigned_at,
            "due_at": assignment.due_at,
            "status": assignment.status,
            "cancelled_by": assignment.cancelled_by,
            "cancelled_at": assignment.cancelled_at,
            "cancellation_reason": assignment.cancellation_reason,
            "created_at": assignment.created_at,
            "updated_at": assignment.updated_at,
        }

    def list_assignments(
        self,
        status: str | None = None,
    ) -> list[dict]:
        if status is None:
            records = self.installation_assignment_repository.get_enriched_records()
        else:
            records = (
                self.installation_assignment_repository
                .get_enriched_records_by_status(status)
            )

        return [
            {
                "id": assignment.id,
                "property_id": assignment.property_id,
                "property_name": property_name,
                "plate_id": assignment.plate_id,
                "plate_code": plate_code,
                "contractor_id": assignment.contractor_id,
                "contractor_name": contractor_name,
                "contractor_member_id": assignment.contractor_member_id,
                "installer_email": installer_email,
                "assigned_by": assignment.assigned_by,
                "assigned_by_email": assigned_by_email,
                "assigned_at": assignment.assigned_at,
                "due_at": assignment.due_at,
                "status": assignment.status,
                "cancelled_by": assignment.cancelled_by,
                "cancelled_at": assignment.cancelled_at,
                "cancellation_reason": assignment.cancellation_reason,
                "created_at": assignment.created_at,
                "updated_at": assignment.updated_at,
            }
            for (
                assignment,
                property_name,
                plate_code,
                contractor_name,
                installer_email,
                assigned_by_email,
            ) in records
        ]
