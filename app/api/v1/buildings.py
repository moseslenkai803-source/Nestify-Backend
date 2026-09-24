from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.property_actions import PropertyAction
from app.db.session import get_db
from app.models.user import User
from app.schemas.building import BuildingCreate, BuildingResponse
from app.services.building_service import BuildingService
from app.services.property_authorization_service import (
    PropertyAuthorizationService,
)


router = APIRouter(
    prefix="/properties/{property_id}/buildings",
    tags=["Buildings"],
)


@router.post(
    "",
    response_model=BuildingResponse,
    status_code=201,
)
def create_building(
    property_id: UUID,
    building_data: BuildingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BuildingService(db)

    try:
        return service.create_building(
            user=current_user,
            property_id=property_id,
            building_number=building_data.building_number,
            name=building_data.name,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Property not found"
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
    response_model=list[BuildingResponse],
)
def list_buildings(
    property_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BuildingService(db)

    try:
        return service.list_buildings(
            user=current_user,
            property_id=property_id,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Property not found"
            else 403
            if str(exc) == "User is not authorized for this property"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.get(
    "/{building_id}",
    response_model=BuildingResponse,
)
def get_building(
    property_id: UUID,
    building_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    authorization_service = PropertyAuthorizationService(db)
    service = BuildingService(db)

    try:
        authorization_service.authorize(
            user=current_user,
            property_id=property_id,
            action=PropertyAction.PROPERTY_MANAGEMENT,
        )

        building = service.get_building(
            building_id=building_id,
        )

        if building.property_id != property_id:
            raise ValueError("Building not found")

        return building

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Property not found",
                "Building not found",
            }
            else 403
            if str(exc) == "User is not authorized for this property"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc
