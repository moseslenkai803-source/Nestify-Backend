from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.employee import (
    EmployeeClearanceCreate,
    EmployeeClearanceResponse,
    EmployeeCreate,
    EmployeeResponse,
)
from app.services.employee_service import EmployeeService


router = APIRouter(
    prefix="/employees",
    tags=["Employees"],
)


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=201,
)
def create_employee(
    employee_data: EmployeeCreate,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)

    try:
        return service.create_employee(
            user_id=employee_data.user_id,
            employee_number=employee_data.employee_number,
            department=employee_data.department,
            position=employee_data.position,
            clearances=employee_data.clearances,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=list[EmployeeResponse],
)
def list_employees(
    active_only: bool = Query(default=False),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)

    return service.list_employees(
        active_only=active_only,
    )


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
)
def get_employee(
    employee_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)

    try:
        return service.get_employee(employee_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{employee_id}/clearances",
    response_model=EmployeeClearanceResponse,
    status_code=201,
)
def add_employee_clearance(
    employee_id: UUID,
    clearance_data: EmployeeClearanceCreate,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)

    try:
        return service.add_clearance(
            employee_id=employee_id,
            clearance=clearance_data.clearance,
        )
    except ValueError as exc:
        detail = str(exc)

        if detail in {
            "Employee not found",
            "Employee user not found",
        }:
            raise HTTPException(
                status_code=404,
                detail=detail,
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=detail,
        ) from exc


@router.get(
    "/{employee_id}/clearances",
    response_model=list[EmployeeClearanceResponse],
)
def list_employee_clearances(
    employee_id: UUID,
    active_only: bool = Query(default=False),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)

    try:
        return service.list_clearances(
            employee_id=employee_id,
            active_only=active_only,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{employee_id}/clearances/{clearance}/remove",
    response_model=EmployeeClearanceResponse,
)
def remove_employee_clearance(
    employee_id: UUID,
    clearance: str,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)

    try:
        return service.remove_clearance(
            employee_id=employee_id,
            clearance=clearance,
        )
    except ValueError as exc:
        detail = str(exc)

        if detail in {
            "Employee not found",
            "Active employee clearance not found",
            "Employee clearance not found",
        }:
            raise HTTPException(
                status_code=404,
                detail=detail,
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=detail,
        ) from exc


@router.post(
    "/{employee_id}/terminate",
    response_model=EmployeeResponse,
)
def terminate_employee(
    employee_id: UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)

    try:
        return service.terminate_employee(employee_id)
    except ValueError as exc:
        detail = str(exc)

        if detail in {
            "Employee not found",
            "Employee user not found",
        }:
            raise HTTPException(
                status_code=404,
                detail=detail,
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=detail,
        ) from exc
