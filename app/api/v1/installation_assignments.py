from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_employee_clearance
from app.db.session import get_db
from app.models.user import User
from app.schemas.installation_assignment import (
    InstallationAssignmentCancel,
    InstallationAssignmentCreate,
    InstallationAssignmentResponse,
    InstallationAssignmentSubmit,
)
from app.schemas.property_installation import PropertyInstallationResponse
from app.services.installation_assignment_query_service import (
    InstallationAssignmentQueryService,
)
from app.services.installation_assignment_service import (
    InstallationAssignmentService,
)


router = APIRouter(
    prefix="/installation-assignments",
    tags=["Installation Assignments"],
)


@router.get(
    "",
    response_model=list[InstallationAssignmentResponse],
)
def list_installation_assignments(
    status: str | None = None,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = InstallationAssignmentQueryService(db)

    return service.list_assignments(status=status)


@router.post(
    "",
    response_model=InstallationAssignmentResponse,
    status_code=201,
)
def create_installation_assignment(
    assignment_data: InstallationAssignmentCreate,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = InstallationAssignmentService(db)

    try:
        assignment = service.create_assignment(
            property_id=assignment_data.property_id,
            plate_id=assignment_data.plate_id,
            contractor_id=assignment_data.contractor_id,
            contractor_member_id=assignment_data.contractor_member_id,
            assigned_by=current_employee.id,
            due_at=assignment_data.due_at,
        )

        query_service = InstallationAssignmentQueryService(db)
        result = query_service.get_assignment(assignment.id)

        if result is None:
            raise HTTPException(
                status_code=500,
                detail="Created installation assignment could not be loaded.",
            )

        return result

    except ValueError as exc:
        status_code = (
            404
            if str(exc)
            in {
                "Property not found",
                "Address plate not found",
                "Contractor not found",
                "Contractor member not found",
                "Contractor member user not found",
                "Assigning employee not found",
            }
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/{assignment_id}/cancel",
    response_model=InstallationAssignmentResponse,
)
def cancel_installation_assignment(
    assignment_id: UUID,
    cancellation_data: InstallationAssignmentCancel,
    current_employee: User = Depends(
        require_employee_clearance("plate_operations")
    ),
    db: Session = Depends(get_db),
):
    service = InstallationAssignmentService(db)

    try:
        assignment = service.cancel_assignment(
            assignment_id=assignment_id,
            cancelled_by=current_employee.id,
            reason=cancellation_data.reason,
        )

        query_service = InstallationAssignmentQueryService(db)
        result = query_service.get_assignment(assignment.id)

        if result is None:
            raise HTTPException(
                status_code=500,
                detail="Cancelled installation assignment could not be loaded.",
            )

        return result
    except ValueError as exc:
        status_code = (
            404
            if str(exc)
            in {
                "Installation assignment not found",
                "Cancelling employee not found",
            }
            else 403
            if str(exc)
            in {
                "Cancelling employee is inactive",
                "Only Nestify employees can cancel installations",
            }
            else 400
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/{assignment_id}/start",
    response_model=InstallationAssignmentResponse,
)
def start_installation_assignment(
    assignment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InstallationAssignmentService(db)

    try:
        assignment = service.start_assignment(
            assignment_id=assignment_id,
            contractor_user_id=current_user.id,
        )

        query_service = InstallationAssignmentQueryService(db)
        result = query_service.get_assignment(assignment.id)

        if result is None:
            raise HTTPException(
                status_code=500,
                detail="Started installation assignment could not be loaded.",
            )

        return result
    except ValueError as exc:
        status_code = (
            404
            if str(exc)
            in {
                "Installation assignment not found",
                "Contractor member not found",
                "Contractor member user not found",
            }
            else 403
            if str(exc)
            in {
                "Contractor user is not assigned to this installation",
                "Contractor member is inactive",
                "Contractor member user is inactive",
                "Contractor member user must be a contractor",
            }
            else 400
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/{assignment_id}/submit",
    response_model=PropertyInstallationResponse,
)
def submit_installation_assignment(
    assignment_id: UUID,
    submission_data: InstallationAssignmentSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InstallationAssignmentService(db)

    try:
        return service.submit_assignment(
            assignment_id=assignment_id,
            contractor_user_id=current_user.id,
            latitude=submission_data.latitude,
            longitude=submission_data.longitude,
            accuracy_meters=submission_data.accuracy_meters,
            captured_at=submission_data.captured_at,
            notes=submission_data.notes,
        )
    except ValueError as exc:
        status_code = (
            404
            if str(exc)
            in {
                "Installation assignment not found",
                "Contractor member not found",
                "Contractor member user not found",
            }
            else 403
            if str(exc)
            in {
                "Contractor user is not assigned to this installation",
                "Contractor member is inactive",
                "Contractor member user is inactive",
                "Contractor member user must be a contractor",
            }
            else 400
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc
