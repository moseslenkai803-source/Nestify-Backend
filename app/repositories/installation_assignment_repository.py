from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.address_plate import AddressPlate
from app.models.contractor import Contractor
from app.models.contractor_member import ContractorMember
from app.models.installation_assignment import InstallationAssignment
from app.models.property import Property
from app.models.user import User


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

    def get_all(self) -> list[InstallationAssignment]:
        return (
            self.db.query(InstallationAssignment)
            .order_by(
                InstallationAssignment.created_at.desc(),
            )
            .all()
        )

    def get_by_status(
        self,
        status: str,
    ) -> list[InstallationAssignment]:
        return (
            self.db.query(InstallationAssignment)
            .filter(
                InstallationAssignment.status == status,
            )
            .order_by(
                InstallationAssignment.created_at.desc(),
            )
            .all()
        )

    def _enriched_statement(self):
        installer = aliased(User)
        assigned_by = aliased(User)

        return (
            select(
                InstallationAssignment,
                Property.name,
                AddressPlate.plate_code,
                Contractor.name,
                installer.email,
                assigned_by.email,
            )
            .join(
                Property,
                Property.id == InstallationAssignment.property_id,
            )
            .join(
                AddressPlate,
                AddressPlate.id == InstallationAssignment.plate_id,
            )
            .join(
                Contractor,
                Contractor.id == InstallationAssignment.contractor_id,
            )
            .join(
                ContractorMember,
                ContractorMember.id
                == InstallationAssignment.contractor_member_id,
            )
            .join(
                installer,
                installer.id == ContractorMember.user_id,
            )
            .join(
                assigned_by,
                assigned_by.id == InstallationAssignment.assigned_by,
            )
        )

    def get_enriched_record_by_id(
        self,
        assignment_id: UUID,
    ) -> tuple | None:
        statement = (
            self._enriched_statement()
            .where(
                InstallationAssignment.id == assignment_id,
            )
        )

        return self.db.execute(statement).first()

    def get_enriched_records(self) -> list[tuple]:
        statement = (
            self._enriched_statement()
            .order_by(
                InstallationAssignment.created_at.desc(),
                InstallationAssignment.id.desc(),
            )
        )

        return self.db.execute(statement).all()

    def get_enriched_records_by_status(
        self,
        status: str,
    ) -> list[tuple]:
        statement = (
            self._enriched_statement()
            .where(
                InstallationAssignment.status == status,
            )
            .order_by(
                InstallationAssignment.created_at.desc(),
                InstallationAssignment.id.desc(),
            )
        )

        return self.db.execute(statement).all()

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
