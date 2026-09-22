import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.property_verification import PropertyVerification
from app.repositories.property_verification_repository import (
    PropertyVerificationRepository,
)
from app.repositories.property_address_repository import PropertyAddressRepository
from app.repositories.property_repository import PropertyRepository


class PropertyVerificationService:
    def __init__(self, db: Session):
        self.db = db
        self.property_repository = PropertyRepository(db)
        self.property_address_repository = PropertyAddressRepository(db)
        self.property_verification_repository = (
            PropertyVerificationRepository(db)
        )

    def verify_property(
        self,
        property_id: uuid.UUID,
        verified_by: uuid.UUID,
        status: str,
        notes: str | None = None,
    ) -> PropertyVerification:
        if status not in {"verified", "rejected"}:
            raise ValueError(
                "Verification status must be 'verified' or 'rejected'"
            )

        property = self.property_repository.get_by_id(property_id)

        if property is None:
            raise ValueError("Property not found")

        address = self.property_address_repository.get_by_property_id(
            property_id
        )

        if address is None:
            raise ValueError(
                "Property must have an address before verification"
            )

        verification = PropertyVerification(
            property_id=property_id,
            verified_by=verified_by,
            status=status,
            verified_at=datetime.now(UTC),
            notes=notes,
        )

        self.property_verification_repository.add(verification)

        if status == "verified":
            property.status = "verified"

        self.db.flush()

        return verification
