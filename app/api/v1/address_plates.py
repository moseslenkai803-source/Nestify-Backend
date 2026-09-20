from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_landlord
from app.db.session import get_db
from app.models.landlord import Landlord
from app.schemas.address_plate import (
    AddressPlateLinkRequest,
    AddressPlateResponse,
)
from app.services.address_plate_service import AddressPlateService
from app.services.property_service import PropertyService


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
    current_landlord: Landlord = Depends(get_current_landlord),
    db: Session = Depends(get_db),
):
    property_service = PropertyService(db)

    try:
        property_service.get_property_for_landlord(
            property_id=link_data.property_id,
            landlord_id=current_landlord.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

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
