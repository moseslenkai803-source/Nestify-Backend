from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.address_plate_request import AddressPlateRequest
from app.models.property import Property
from app.models.user import User


class AddressPlateRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        request: AddressPlateRequest,
    ) -> AddressPlateRequest:
        self.db.add(request)
        self.db.flush()

        return request

    def get_by_id(
        self,
        request_id: UUID,
    ) -> AddressPlateRequest | None:
        return self.db.get(
            AddressPlateRequest,
            request_id,
        )

    def get_by_id_for_update(
        self,
        request_id: UUID,
    ) -> AddressPlateRequest | None:
        statement = (
            select(AddressPlateRequest)
            .where(AddressPlateRequest.id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.db.scalar(statement)

    def get_by_property_id(
        self,
        property_id: UUID,
    ) -> list[AddressPlateRequest]:
        return (
            self.db.query(AddressPlateRequest)
            .filter(
                AddressPlateRequest.property_id == property_id,
            )
            .order_by(
                AddressPlateRequest.requested_at.desc(),
            )
            .all()
        )

    def get_by_status(
        self,
        status: str,
    ) -> list[AddressPlateRequest]:
        return (
            self.db.query(AddressPlateRequest)
            .filter(
                AddressPlateRequest.status == status,
            )
            .order_by(
                AddressPlateRequest.requested_at.desc(),
            )
            .all()
        )

    def get_enriched_by_status(
        self,
        status: str,
    ) -> list[tuple[AddressPlateRequest, str, str, str]]:
        statement = (
            select(
                AddressPlateRequest,
                Property.name,
                Property.property_code,
                User.email,
            )
            .join(
                Property,
                Property.id == AddressPlateRequest.property_id,
            )
            .join(
                User,
                User.id == AddressPlateRequest.requested_by,
            )
            .where(AddressPlateRequest.status == status)
            .order_by(AddressPlateRequest.requested_at.desc())
        )

        return list(self.db.execute(statement).all())

    def get_pending_by_property_id(
        self,
        property_id: UUID,
    ) -> AddressPlateRequest | None:
        return (
            self.db.query(AddressPlateRequest)
            .filter(
                AddressPlateRequest.property_id == property_id,
                AddressPlateRequest.status == "pending",
            )
            .first()
        )
