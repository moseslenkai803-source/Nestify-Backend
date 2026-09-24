from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.space import SpaceCreate, SpaceResponse
from app.services.space_service import SpaceService


router = APIRouter(
    prefix="/properties/{property_id}/buildings/{building_id}/floors/{floor_id}/spaces",
    tags=["Spaces"],
)


@router.post(
    "",
    response_model=SpaceResponse,
    status_code=201,
)
def create_space(
    property_id: UUID,
    building_id: UUID,
    floor_id: UUID,
    space_data: SpaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SpaceService(db)

    try:
        return service.create_space(
            user=current_user,
            property_id=property_id,
            building_id=building_id,
            floor_id=floor_id,
            space_number=space_data.space_number,
            name=space_data.name,
            space_type=space_data.space_type,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Property not found",
                "Building not found",
                "Floor not found",
                "Space not found",
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
    response_model=list[SpaceResponse],
)
def list_spaces(
    property_id: UUID,
    building_id: UUID,
    floor_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SpaceService(db)

    try:
        return service.list_spaces(
            user=current_user,
            property_id=property_id,
            building_id=building_id,
            floor_id=floor_id,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Property not found",
                "Building not found",
                "Floor not found",
                "Space not found",
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
    "/{space_id}",
    response_model=SpaceResponse,
)
def get_space(
    property_id: UUID,
    building_id: UUID,
    floor_id: UUID,
    space_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SpaceService(db)

    try:
        return service.get_space(
            user=current_user,
            property_id=property_id,
            building_id=building_id,
            floor_id=floor_id,
            space_id=space_id,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Property not found",
                "Building not found",
                "Floor not found",
                "Space not found",
            }
            else 403
            if str(exc) == "User is not authorized for this property"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc
