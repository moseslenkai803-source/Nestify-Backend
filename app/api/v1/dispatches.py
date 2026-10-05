from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_clearance
from app.db.session import get_db
from app.models.user import User
from app.schemas.address_plate import AddressPlateResponse
from app.schemas.dispatch import DispatchCreate, DispatchResponse
from app.services.dispatch_service import DispatchService


router = APIRouter(
    prefix="/dispatches",
    tags=["Dispatches"],
)


@router.post(
    "",
    response_model=DispatchResponse,
    status_code=201,
)
def create_dispatch(
    dispatch_data: DispatchCreate,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = DispatchService(db)

    try:
        return service.create_dispatch(
            plate_ids=dispatch_data.plate_ids,
            destination=dispatch_data.destination,
            recipient_name=dispatch_data.recipient_name,
            recipient_phone=dispatch_data.recipient_phone,
            tracking_reference=dispatch_data.tracking_reference,
            created_by=current_employee.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=list[DispatchResponse],
)
def list_dispatches(
    status: str | None = None,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = DispatchService(db)

    try:
        return service.list_dispatches(status=status)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/{dispatch_code}/plates",
    response_model=list[AddressPlateResponse],
)
def get_dispatch_plates(
    dispatch_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = DispatchService(db)

    try:
        return service.get_dispatch_plates(dispatch_code)

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get(
    "/{dispatch_code}",
    response_model=DispatchResponse,
)
def get_dispatch(
    dispatch_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = DispatchService(db)

    try:
        return service.get_dispatch(dispatch_code)

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{dispatch_code}/ready",
    response_model=DispatchResponse,
)
def mark_dispatch_ready(
    dispatch_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = DispatchService(db)

    try:
        return service.mark_ready(dispatch_code)

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Dispatch not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/{dispatch_code}/dispatch",
    response_model=DispatchResponse,
)
def mark_dispatch_dispatched(
    dispatch_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = DispatchService(db)

    try:
        return service.mark_dispatched(
            dispatch_code=dispatch_code,
            performed_by=current_employee.id,
        )

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Dispatch not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/{dispatch_code}/deliver",
    response_model=DispatchResponse,
)
def mark_dispatch_delivered(
    dispatch_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = DispatchService(db)

    try:
        return service.mark_delivered(dispatch_code)

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Dispatch not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/{dispatch_code}/cancel",
    response_model=DispatchResponse,
)
def cancel_dispatch(
    dispatch_code: str,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = DispatchService(db)

    try:
        return service.cancel_dispatch(dispatch_code)

    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Dispatch not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc
