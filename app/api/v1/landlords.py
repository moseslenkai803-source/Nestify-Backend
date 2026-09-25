from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.landlord import LandlordOnboardRequest, LandlordResponse
from app.services.registration_service import RegistrationService

router = APIRouter(prefix="/landlords", tags=["landlords"])


@router.post("/onboard", response_model=LandlordResponse, status_code=201)
def onboard_landlord(
    payload: LandlordOnboardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Onboard an existing active user account as an operational Landlord profile.
    """
    registration_service = RegistrationService(db)
    try:
        landlord = registration_service.onboard_existing_user(
            user_id=current_user.id,
            display_name=payload.display_name,
            phone=payload.phone,
            landlord_type=payload.landlord_type,
        )
        return landlord
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
