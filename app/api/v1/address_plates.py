from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_clearance
from app.db.session import get_db
from app.models.user import User
from app.schemas.address_plate import (
    AddressPlateLinkRequest,
    AddressPlateResponse,
)
from app.services.address_plate_service import AddressPlateService


router = APIRouter(
    prefix="/address-plates",
    tags=["Address Plates"],
)


@router.post(
    "",
    response_model=AddressPlateResponse,
    status_code=201,
)
def create_address_plate(
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = AddressPlateService(db)

    return service.create_plate()


@router.get(
    "/{plate_code}",
    response_model=AddressPlateResponse,
)
def get_address_plate(
    plate_code: str,
    db: Session = Depends(get_db),
):
    service = AddressPlateService(db)

    plate = service.get_plate_by_code(plate_code)

    if plate is None:
        raise HTTPException(
            status_code=404,
            detail="Plate not found",
        )

    return plate


@router.post(
    "/{plate_code}/verify",
    response_model=AddressPlateResponse,
)
def verify_address_plate(
    plate_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = AddressPlateService(db)

    try:
        return service.verify_plate(plate_code)

    except ValueError as exc:
        raise HTTPException(
            status_code=404 if str(exc) == "Plate not found" else 400,
            detail=str(exc),
        ) from exc


@router.post(
    "/{plate_code}/link",
    response_model=AddressPlateResponse,
)
def link_address_plate(
    plate_code: str,
    link_data: AddressPlateLinkRequest,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = AddressPlateService(db)

    try:
        return service.link_plate_to_property(
            plate_code=plate_code,
            property_id=link_data.property_id,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Plate not found",
                "Property not found",
            }
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc
