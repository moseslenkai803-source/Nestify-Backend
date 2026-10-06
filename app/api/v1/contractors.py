from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_employee_clearance
from app.db.session import get_db
from app.models.user import User
from app.schemas.contractor import (
    ContractorCreate,
    ContractorMemberCandidateResponse,
    ContractorMemberCreate,
    ContractorMemberResponse,
    ContractorResponse,
)
from app.services.contractor_service import ContractorService


router = APIRouter(
    prefix="/contractors",
    tags=["Contractors"],
)


@router.post(
    "",
    response_model=ContractorResponse,
    status_code=201,
)
def create_contractor(
    contractor_data: ContractorCreate,
    current_employee: User = Depends(
        require_employee_clearance("contractor_management")
    ),
    db: Session = Depends(get_db),
):
    service = ContractorService(db)

    try:
        return service.create_contractor(
            name=contractor_data.name,
            contractor_type=contractor_data.contractor_type,
            contact_email=contractor_data.contact_email,
            contact_phone=contractor_data.contact_phone,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/{contractor_id}/deactivate",
    response_model=ContractorResponse,
)
def deactivate_contractor(
    contractor_id: UUID,
    current_employee: User = Depends(
        require_employee_clearance("contractor_management")
    ),
    db: Session = Depends(get_db),
):
    service = ContractorService(db)

    try:
        return service.deactivate_contractor(contractor_id)
    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Contractor not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/{contractor_id}/reactivate",
    response_model=ContractorResponse,
)
def reactivate_contractor(
    contractor_id: UUID,
    current_employee: User = Depends(
        require_employee_clearance("contractor_management")
    ),
    db: Session = Depends(get_db),
):
    service = ContractorService(db)

    try:
        return service.reactivate_contractor(contractor_id)
    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Contractor not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=list[ContractorResponse],
)
def list_contractors(
    active_only: bool = Query(default=False),
    current_employee: User = Depends(
        require_employee_clearance("contractor_management")
    ),
    db: Session = Depends(get_db),
):
    service = ContractorService(db)

    return service.list_contractors(
        active_only=active_only,
    )


@router.get(
    "/candidates",
    response_model=list[ContractorMemberCandidateResponse],
)
def list_contractor_candidates(
    current_employee: User = Depends(
        require_employee_clearance("contractor_management")
    ),
    db: Session = Depends(get_db),
):
    service = ContractorService(db)

    return service.list_contractor_candidates()


@router.get(
    "/{contractor_id}",
    response_model=ContractorResponse,
)
def get_contractor(
    contractor_id: UUID,
    current_employee: User = Depends(
        require_employee_clearance("contractor_management")
    ),
    db: Session = Depends(get_db),
):
    service = ContractorService(db)

    try:
        return service.get_contractor(contractor_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get(
    "/{contractor_id}/members",
    response_model=list[ContractorMemberResponse],
)
def list_contractor_members(
    contractor_id: UUID,
    current_employee: User = Depends(
        require_employee_clearance("contractor_management")
    ),
    db: Session = Depends(get_db),
):
    service = ContractorService(db)

    try:
        return service.list_members(contractor_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/{contractor_id}/members",
    response_model=ContractorMemberResponse,
    status_code=201,
)
def add_contractor_member(
    contractor_id: UUID,
    member_data: ContractorMemberCreate,
    current_employee: User = Depends(
        require_employee_clearance("contractor_management")
    ),
    db: Session = Depends(get_db),
):
    service = ContractorService(db)

    try:
        return service.add_member(
            contractor_id=contractor_id,
            user_id=member_data.user_id,
        )
    except ValueError as exc:
        status_code = (
            404
            if str(exc)
            in {
                "Contractor not found",
                "User not found",
            }
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/{contractor_id}/members/{user_id}/deactivate",
    response_model=ContractorMemberResponse,
)
def deactivate_contractor_member(
    contractor_id: UUID,
    user_id: UUID,
    current_employee: User = Depends(
        require_employee_clearance("contractor_management")
    ),
    db: Session = Depends(get_db),
):
    service = ContractorService(db)

    try:
        return service.deactivate_member(
            contractor_id=contractor_id,
            user_id=user_id,
        )
    except ValueError as exc:
        status_code = (
            404
            if str(exc) == "Active contractor membership not found"
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc
