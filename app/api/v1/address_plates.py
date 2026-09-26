from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_clearance
from app.db.session import get_db
from app.models.user import User
from app.schemas.address_plate import (
    AddressPlateResponse,
)
from app.services.address_plate_service import AddressPlateService
from app.services.property_access_service import PropertyAccessService


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
