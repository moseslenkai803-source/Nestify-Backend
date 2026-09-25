import uuid
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

    def onboard_existing_user(
        self,
        user_id: uuid.UUID,
        display_name: str,
        phone: str,
        landlord_type: str = "individual",
    ) -> Landlord:
        import uuid
        
        # 1. Verify user existence
        user = self.user_service.user_repository.get_by_id(user_id)
        if user is None:
            raise ValueError("User not found")

        # 2. Guard against duplicate landlord profiles
        existing_landlord = self.landlord_repository.get_by_user_id(user_id)
        if existing_landlord is not None:
            raise ValueError("User is already registered as a landlord")

        # 3. Create and persist the landlord profile
        landlord = Landlord(
            user_id=user_id,
            display_name=display_name,
            phone=phone,
            landlord_type=landlord_type,
        )
        landlord = self.landlord_repository.add(landlord)

        # 4. Elevate or align system permissions role
        user.role = "landlord"
        
        return landlord
