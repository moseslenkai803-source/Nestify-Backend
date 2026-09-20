from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_landlord
from app.db.session import get_db
from app.models.landlord import Landlord
from app.schemas.address_plate import AddressPlateResponse
from app.schemas.property import PropertyCreate, PropertyResponse
from app.schemas.property_activation import PropertyActivationRequest
from app.schemas.property_address import (
    PropertyAddressCreate,
    PropertyAddressResponse,
)
from app.services.property_address_service import PropertyAddressService
from app.services.property_activation_service import PropertyActivationService
from app.services.property_service import PropertyService


router = APIRouter(
    prefix="/properties",
    tags=["Properties"],
)


@router.post(
    "",
    response_model=PropertyResponse,
    status_code=201,
)
def create_property(
    property_data: PropertyCreate,
    current_landlord: Landlord = Depends(get_current_landlord),
    db: Session = Depends(get_db),
):
    service = PropertyService(db)

    try:
        return service.create_property(
            landlord_id=current_landlord.id,
            name=property_data.name,
            property_type=property_data.property_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{property_id}/activate",
    response_model=AddressPlateResponse,
)
def activate_property(
    property_id: UUID,
    activation_data: PropertyActivationRequest,
    current_landlord: Landlord = Depends(get_current_landlord),
    db: Session = Depends(get_db),
):
    service = PropertyActivationService(db)

    try:
        property = service.property_service.get_property(property_id)

        if property.landlord_id != current_landlord.id:
            raise HTTPException(
                status_code=404,
                detail="Property not found",
            )

        return service.activate_property(
            property_id=property_id,
            plate_code=activation_data.plate_code,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Property not found",
                "Plate not found",
            }
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/{property_id}/address",
    response_model=PropertyAddressResponse,
    status_code=201,
)
def create_property_address(
    property_id: UUID,
    address_data: PropertyAddressCreate,
    current_landlord: Landlord = Depends(get_current_landlord),
    db: Session = Depends(get_db),
):
    service = PropertyAddressService(db)

    try:
        property = service.property_repository.get_by_id(property_id)

        if property is None:
            raise HTTPException(
                status_code=404,
                detail="Property not found",
            )

        if property.landlord_id != current_landlord.id:
            raise HTTPException(
                status_code=404,
                detail="Property not found",
            )

        return service.create_address(
            property_id=property_id,
            formatted_address=address_data.formatted_address,
            county=address_data.county,
            sub_county=address_data.sub_county,
            locality=address_data.locality,
            latitude=address_data.latitude,
            longitude=address_data.longitude,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get(
    "/{property_id}/address",
    response_model=PropertyAddressResponse,
)
def get_property_address(
    property_id: UUID,
    current_landlord: Landlord = Depends(get_current_landlord),
    db: Session = Depends(get_db),
):
    service = PropertyAddressService(db)

    try:
        property = service.property_repository.get_by_id(property_id)

        if property is None:
            raise HTTPException(
                status_code=404,
                detail="Property not found",
            )

        if property.landlord_id != current_landlord.id:
            raise HTTPException(
                status_code=404,
                detail="Property not found",
            )

        address = service.property_address_repository.get_by_property_id(
            property_id
        )

        if address is None:
            raise ValueError("Property address not found")

        return address

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=list[PropertyResponse],
)
def list_properties(
    current_landlord: Landlord = Depends(get_current_landlord),
    db: Session = Depends(get_db),
):
    service = PropertyService(db)

    try:
        return service.list_properties(
            current_landlord.id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get(
    "/{property_id}",
    response_model=PropertyResponse,
)
def get_property(
    property_id: UUID,
    current_landlord: Landlord = Depends(get_current_landlord),
    db: Session = Depends(get_db),
):
    service = PropertyService(db)

    try:
        property = service.get_property(property_id)

        if property.landlord_id != current_landlord.id:
            raise HTTPException(
                status_code=404,
                detail="Property not found",
            )

        return property
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
