from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_clearance
from app.db.session import get_db
from app.models.user import User
from app.repositories.address_plate_request_repository import (
    AddressPlateRequestRepository,
)
from app.schemas.address_plate import AddressPlateResponse
from app.services.address_plate_allocation_service import (
    AddressPlateAllocationService,
)
from app.services.property_access_service import PropertyAccessService


router = APIRouter(
    prefix="/address-plate-requests",
    tags=["Address Plate Allocation"],
)


@router.post(
    "/{request_id}/allocate",
    response_model=AddressPlateResponse,
)
def allocate_address_plate(
    request_id: UUID,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    request_repository = AddressPlateRequestRepository(db)
    request = request_repository.get_by_id(request_id)

    if request is None:
        raise HTTPException(
            status_code=404,
            detail="Address plate request not found",
        )

    access_service = PropertyAccessService(db)

    try:
        access_service.authorize(
            user_id=current_employee.id,
            property_id=request.property_id,
            access_type="plate_operations",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    service = AddressPlateAllocationService(db)

    try:
        return service.allocate_plate(
            request_id=request_id,
            performed_by=current_employee.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
