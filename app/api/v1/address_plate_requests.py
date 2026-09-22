from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_clearance
from app.db.session import get_db
from app.models.user import User
from app.schemas.address_plate import AddressPlateRequestResponse
from app.services.address_plate_request_service import AddressPlateRequestService


router = APIRouter(
    prefix="/address-plate-requests",
    tags=["Address Plate Requests"],
)


@router.post(
    "/{request_id}/approve",
    response_model=AddressPlateRequestResponse,
)
def approve_address_plate_request(
    request_id: UUID,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = AddressPlateRequestService(db)

    try:
        return service.approve_request(request_id)

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Address plate request not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/{request_id}/reject",
    response_model=AddressPlateRequestResponse,
)
def reject_address_plate_request(
    request_id: UUID,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = AddressPlateRequestService(db)

    try:
        return service.reject_request(request_id)

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Address plate request not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc
