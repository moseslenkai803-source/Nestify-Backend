from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_clearance
from app.core.exceptions import (
    AddressPlateRequestNotFoundError,
    PropertyAccessDeniedError,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.address_plate import AddressPlateResponse
from app.services.address_plate_allocation_service import (
    AddressPlateAllocationService,
)


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
    service = AddressPlateAllocationService(db)

    try:
        return service.allocate_plate(
            request_id=request_id,
            user=current_employee,
        )
    except AddressPlateRequestNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except PropertyAccessDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
