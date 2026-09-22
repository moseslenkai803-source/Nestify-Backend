from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_clearance
from app.db.session import get_db
from app.models.user import User
from app.schemas.address_plate import AddressPlateResponse
from app.schemas.manufacturing_order import (
    ManufacturingOrderCreate,
    ManufacturingOrderResponse,
)
from app.services.manufacturing_order_service import (
    ManufacturingOrderService,
)


router = APIRouter(
    prefix="/manufacturing-orders",
    tags=["Manufacturing Orders"],
)


@router.post(
    "",
    response_model=ManufacturingOrderResponse,
    status_code=201,
)
def create_manufacturing_order(
    order_data: ManufacturingOrderCreate,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = ManufacturingOrderService(db)

    try:
        return service.create_order(
            quantity=order_data.quantity,
            created_by=current_employee.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/{order_code}",
    response_model=ManufacturingOrderResponse,
)
def get_manufacturing_order(
    order_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = ManufacturingOrderService(db)

    try:
        return service.get_order(order_code)

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{order_code}/approve",
    response_model=ManufacturingOrderResponse,
)
def approve_manufacturing_order(
    order_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = ManufacturingOrderService(db)

    try:
        return service.approve_order(
            order_code=order_code,
            approved_by=current_employee.id,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Manufacturing order not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc

@router.post(
    "/{order_code}/start",
    response_model=ManufacturingOrderResponse,
)
def start_manufacturing_order(
    order_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = ManufacturingOrderService(db)

    try:
        return service.start_order(
            order_code=order_code,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Manufacturing order not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc

@router.post(
    "/{order_code}/complete",
    response_model=ManufacturingOrderResponse,
)
def complete_manufacturing_order(
    order_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = ManufacturingOrderService(db)

    try:
        return service.complete_order(
            order_code=order_code,
            completed_by=current_employee.id,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Manufacturing order not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc

@router.post(
    "/{order_code}/cancel",
    response_model=ManufacturingOrderResponse,
)
def cancel_manufacturing_order(
    order_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = ManufacturingOrderService(db)

    try:
        return service.cancel_order(
            order_code=order_code,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Manufacturing order not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc

@router.get(
    "/{order_code}/plates",
    response_model=list[AddressPlateResponse],
)
def get_manufacturing_order_plates(
    order_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = ManufacturingOrderService(db)

    try:
        return service.get_order_plates(order_code)

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
