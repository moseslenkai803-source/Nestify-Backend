from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.installation_assignment import InstallationAssignment


class InstallationAssignmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        assignment: InstallationAssignment,
    ) -> InstallationAssignment:
        self.db.add(assignment)
        self.db.flush()

        return assignment

    def get_by_id(
        self,
        assignment_id: UUID,
    ) -> InstallationAssignment | None:
        return self.db.get(
            InstallationAssignment,
            assignment_id,
        )

    def get_by_id_for_update(
        self,
        assignment_id: UUID,
    ) -> InstallationAssignment | None:
        statement = (
            select(InstallationAssignment)
            .where(InstallationAssignment.id == assignment_id)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_active_by_property_id(
        self,
        property_id: UUID,
    ) -> InstallationAssignment | None:
        return self.db.scalar(
            select(InstallationAssignment)
            .where(
                InstallationAssignment.property_id == property_id,
                InstallationAssignment.status.in_(
                    ["assigned", "in_progress", "submitted"]
                ),
            )
            .order_by(
                InstallationAssignment.created_at.desc(),
                InstallationAssignment.id.desc(),
            )
        )

    def get_active_by_plate_id(
        self,
        plate_id: UUID,
    ) -> InstallationAssignment | None:
        return self.db.scalar(
            select(InstallationAssignment)
            .where(
                InstallationAssignment.plate_id == plate_id,
                InstallationAssignment.status.in_(
                    ["assigned", "in_progress", "submitted"]
                ),
            )
            .order_by(
                InstallationAssignment.created_at.desc(),
                InstallationAssignment.id.desc(),
            )
        )

    def get_by_contractor_id(
        self,
        contractor_id: UUID,
    ) -> list[InstallationAssignment]:
        return (
            self.db.query(InstallationAssignment)
            .filter(
                InstallationAssignment.contractor_id == contractor_id,
            )
            .order_by(
                InstallationAssignment.created_at.desc(),
            )
            .all()
        )

    def get_by_contractor_member_id(
        self,
        contractor_member_id: UUID,
    ) -> list[InstallationAssignment]:
        return (
            self.db.query(InstallationAssignment)
            .filter(
                InstallationAssignment.contractor_member_id == contractor_member_id,
            )
            .order_by(
                InstallationAssignment.created_at.desc(),
            )
            .all()
        )

    def get_by_property_id(
        self,
        property_id: UUID,
    ) -> list[InstallationAssignment]:
        return (
            self.db.query(InstallationAssignment)
            .filter(
                InstallationAssignment.property_id == property_id,
            )
            .order_by(
                InstallationAssignment.created_at.desc(),
            )
            .all()
        )
