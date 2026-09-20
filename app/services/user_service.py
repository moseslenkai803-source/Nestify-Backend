from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, db: Session):
        self.user_repository = UserRepository(db)

    def create_user(
        self,
        email: str,
        password: str,
        role: str = "landlord",
    ) -> User:
        existing_user = self.user_repository.get_by_email(email)

        if existing_user is not None:
            raise ValueError("User with this email already exists")

        password_hash = hash_password(password)

        user = User(
            email=email,
            password_hash=password_hash,
            role=role,
            is_active=True,
        )

        return self.user_repository.add(user)
