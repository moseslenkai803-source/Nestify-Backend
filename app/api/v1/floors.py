from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.floor import FloorCreate, FloorResponse
from app.services.floor_service import FloorService


router = APIRouter(
    prefix="/properties/{property_id}/buildings/{building_id}/floors",
    tags=["Floors"],
)


@router.post(
    "",
    response_model=FloorResponse,
    status_code=201,
)
def create_floor(
    property_id: UUID,
    building_id: UUID,
    floor_data: FloorCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = FloorService(db)

    try:
        return service.create_floor(
            user=current_user,
            property_id=property_id,
            building_id=building_id,
            floor_number=floor_data.floor_number,
            name=floor_data.name,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Property not found",
                "Building not found",
                "Floor not found",
            }
            else 403
            if str(exc) == "User is not authorized for this property"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=list[FloorResponse],
)
def list_floors(
    property_id: UUID,
    building_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = FloorService(db)

    try:
        return service.list_floors(
            user=current_user,
            property_id=property_id,
            building_id=building_id,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Property not found",
                "Building not found",
                "Floor not found",
            }
            else 403
            if str(exc) == "User is not authorized for this property"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.get(
    "/{floor_id}",
    response_model=FloorResponse,
)
def get_floor(
    property_id: UUID,
    building_id: UUID,
    floor_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = FloorService(db)

    try:
        floor = service.get_floor(
            user=current_user,
            property_id=property_id,
            floor_id=floor_id,
        )

        if floor.building_id != building_id:
            raise ValueError("Floor not found")

        return floor

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Property not found",
                "Building not found",
                "Floor not found",
            }
            else 403
            if str(exc) == "User is not authorized for this property"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc
