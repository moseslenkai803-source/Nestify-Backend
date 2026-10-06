from uuid import UUID

from sqlalchemy.orm import Session

from app.models.contractor import Contractor
from app.models.user import User
from app.models.contractor_member import ContractorMember
from app.repositories.contractor_member_repository import (
    ContractorMemberRepository,
)
from app.repositories.contractor_repository import ContractorRepository
from app.repositories.user_repository import UserRepository


class ContractorService:
    def __init__(self, db: Session):
        self.db = db
        self.contractor_repository = ContractorRepository(db)
        self.contractor_member_repository = ContractorMemberRepository(db)
        self.user_repository = UserRepository(db)

    def list_contractor_candidates(self) -> list[User]:
        return self.contractor_repository.get_candidate_users()

    def create_contractor(
        self,
        name: str,
        contractor_type: str = "company",
        contact_email: str | None = None,
        contact_phone: str | None = None,
    ) -> Contractor:
        if not name.strip():
            raise ValueError("Contractor name is required")

        if not contractor_type.strip():
            raise ValueError("Contractor type is required")

        contractor = Contractor(
            name=name.strip(),
            contractor_type=contractor_type.strip(),
            status="active",
            contact_email=contact_email,
            contact_phone=contact_phone,
        )

        return self.contractor_repository.add(contractor)

    def add_member(
        self,
        contractor_id: UUID,
        user_id: UUID,
    ) -> ContractorMember:
        contractor = self.contractor_repository.get_by_id_for_update(
            contractor_id
        )

        if contractor is None:
            raise ValueError("Contractor not found")

        if contractor.status != "active":
            raise ValueError("Contractor is inactive")

        user = self.user_repository.get_by_id(user_id)

        if user is None:
            raise ValueError("User not found")

        if not user.is_active:
            raise ValueError("User is inactive")

        if user.role != "contractor":
            raise ValueError(
                "Only contractor users can be contractor members"
            )

        existing_member = (
            self.contractor_member_repository
            .get_by_contractor_and_user_for_update(
                contractor_id=contractor_id,
                user_id=user_id,
            )
        )

        if existing_member is not None:
            if existing_member.is_active:
                raise ValueError(
                    "User is already an active member of this contractor"
                )

            existing_member.is_active = True
            self.db.flush()
            return existing_member

        contractor_member = ContractorMember(
            contractor_id=contractor_id,
            user_id=user_id,
            is_active=True,
        )

        return self.contractor_member_repository.add(
            contractor_member
        )

    def deactivate_contractor(
        self,
        contractor_id: UUID,
    ) -> Contractor:
        contractor = self.contractor_repository.get_by_id_for_update(
            contractor_id
        )

        if contractor is None:
            raise ValueError("Contractor not found")

        if contractor.status == "inactive":
            raise ValueError("Contractor is already inactive")

        contractor.status = "inactive"
        self.db.flush()

        return contractor

    def get_contractor(
        self,
        contractor_id: UUID,
    ) -> Contractor:
        contractor = self.contractor_repository.get_by_id(
            contractor_id
        )

        if contractor is None:
            raise ValueError("Contractor not found")

        return contractor

    def list_contractors(
        self,
        active_only: bool = False,
    ) -> list[Contractor]:
        if active_only:
            return self.contractor_repository.get_active()

        return self.contractor_repository.get_all()

    def list_members(
        self,
        contractor_id: UUID,
    ) -> list[ContractorMember]:
        contractor = self.contractor_repository.get_by_id(
            contractor_id
        )

        if contractor is None:
            raise ValueError("Contractor not found")

        return self.contractor_member_repository.get_by_contractor_id(
            contractor_id
        )

    def deactivate_member(
        self,
        contractor_id: UUID,
        user_id: UUID,
    ) -> ContractorMember:
        member = (
            self.contractor_member_repository
            .get_by_contractor_and_user_for_update(
                contractor_id=contractor_id,
                user_id=user_id,
            )
        )

        if member is None or not member.is_active:
            raise ValueError(
                "Active contractor membership not found"
            )

        return self.contractor_member_repository.deactivate(member)
