from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.landlord import Landlord
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.landlord_repository import LandlordRepository


bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        ) from exc

    subject = payload.get("sub")

    if subject is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        ) from exc

    user_repository = UserRepository(db)

    user = user_repository.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User account is inactive",
        )

    return user


def get_current_landlord(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Landlord:
    landlord_repository = LandlordRepository(db)

    landlord = landlord_repository.get_by_user_id(
        current_user.id
    )

    if landlord is None:
        raise HTTPException(
            status_code=404,
            detail="Landlord profile not found",
        )

    return landlord
