from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.listing import (
    ListingCreate,
    ListingResponse,
    listing_to_response,
)
from app.services.listing_service import ListingService


router = APIRouter(
    tags=["Listings"],
)


@router.post(
    "/properties/{property_id}/listings",
    response_model=ListingResponse,
    status_code=201,
)
def create_property_listing(
    property_id: UUID,
    listing_data: ListingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ListingService(db)

    try:
        listing = service.create_property_listing(
            user=current_user,
            property_id=property_id,
            transaction_type=listing_data.transaction_type,
            title=listing_data.title,
            description=listing_data.description,
        )

        return listing_to_response(listing)

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Property not found",
            }
            else 403
            if str(exc) == "User is not authorized for this property"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/properties/{property_id}/buildings/{building_id}/floors/{floor_id}/listings",
    response_model=ListingResponse,
    status_code=201,
)
def create_floor_listing(
    property_id: UUID,
    building_id: UUID,
    floor_id: UUID,
    listing_data: ListingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ListingService(db)

    try:
        listing = service.create_floor_listing(
            user=current_user,
            property_id=property_id,
            building_id=building_id,
            floor_id=floor_id,
            transaction_type=listing_data.transaction_type,
            title=listing_data.title,
            description=listing_data.description,
        )

        return listing_to_response(listing)

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Property not found",
                "Floor not found",
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


@router.post(
    "/properties/{property_id}/buildings/{building_id}/floors/{floor_id}/spaces/{space_id}/listings",
    response_model=ListingResponse,
    status_code=201,
)
def create_space_listing(
    property_id: UUID,
    building_id: UUID,
    floor_id: UUID,
    space_id: UUID,
    listing_data: ListingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ListingService(db)

    try:
        listing = service.create_space_listing(
            user=current_user,
            property_id=property_id,
            building_id=building_id,
            floor_id=floor_id,
            space_id=space_id,
            transaction_type=listing_data.transaction_type,
            title=listing_data.title,
            description=listing_data.description,
        )

        return listing_to_response(listing)

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


@router.post(
    "/listings/{listing_id}/publish",
    response_model=ListingResponse,
)
def publish_listing(
    listing_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ListingService(db)

    try:
        listing = service.publish_listing(
            user=current_user,
            listing_id=listing_id,
        )

        return listing_to_response(listing)

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Listing not found",
                "Property not found",
                "Floor not found",
                "Building not found",
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


@router.post(
    "/listings/{listing_id}/unpublish",
    response_model=ListingResponse,
)
def unpublish_listing(
    listing_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ListingService(db)

    try:
        listing = service.unpublish_listing(
            user=current_user,
            listing_id=listing_id,
        )

        return listing_to_response(listing)

    except ValueError as exc:
        status_code = (
            404
            if str(exc) in {
                "Listing not found",
                "Property not found",
                "Floor not found",
                "Building not found",
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
