from sqlalchemy.orm import Session

from app.models.landlord import Landlord
from app.models.user import User
from app.repositories.landlord_repository import LandlordRepository
from app.services.user_service import UserService


class RegistrationService:
    def __init__(self, db: Session):
        self.user_service = UserService(db)
        self.landlord_repository = LandlordRepository(db)

    def register_landlord(
        self,
        email: str,
        password: str,
        display_name: str,
        phone: str,
        landlord_type: str = "individual",
    ) -> tuple[User, Landlord]:
        user = self.user_service.create_user(
            email=email,
            password=password,
            role="landlord",
        )

        landlord = Landlord(
            user_id=user.id,
            display_name=display_name,
            phone=phone,
            landlord_type=landlord_type,
        )

        landlord = self.landlord_repository.add(landlord)

        return user, landlord
