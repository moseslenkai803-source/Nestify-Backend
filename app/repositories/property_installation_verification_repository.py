from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.property_installation_verification import (
    PropertyInstallationVerification,
)


class PropertyInstallationVerificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        verification: PropertyInstallationVerification,
    ) -> PropertyInstallationVerification:
        self.db.add(verification)
        self.db.flush()
        return verification

    def get_by_id(
        self,
        verification_id: UUID,
    ) -> PropertyInstallationVerification | None:
        return self.db.scalar(
            select(PropertyInstallationVerification).where(
                PropertyInstallationVerification.id == verification_id
            )
        )

    def get_by_installation_id(
        self,
        installation_id: UUID,
    ) -> list[PropertyInstallationVerification]:
        return list(
            self.db.scalars(
                select(PropertyInstallationVerification)
                .where(
                    PropertyInstallationVerification.installation_id
                    == installation_id
                )
                .order_by(
                    PropertyInstallationVerification.created_at.desc()
                )
            ).all()
        )

    def get_latest_by_installation_id(
        self,
        installation_id: UUID,
    ) -> PropertyInstallationVerification | None:
        return self.db.scalar(
            select(PropertyInstallationVerification)
            .where(
                PropertyInstallationVerification.installation_id
                == installation_id
            )
            .order_by(
                PropertyInstallationVerification.created_at.desc()
            )
            .limit(1)
        )
