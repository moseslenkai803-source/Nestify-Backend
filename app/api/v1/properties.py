from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.property import PropertyCreate, PropertyResponse
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
    landlord_id: UUID,
    db: Session = Depends(get_db),
):
    service = PropertyService(db)

    try:
        return service.create_property(
            landlord_id=landlord_id,
            name=property_data.name,
            property_type=property_data.property_type,
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
    db: Session = Depends(get_db),
):
    service = PropertyService(db)

    try:
        return service.get_property(property_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
