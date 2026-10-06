from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_id_for_update(
        self,
        user_id: UUID,
    ) -> User | None:
        statement = (
            select(User)
            .where(User.id == user_id)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def get_by_email(self, email: str) -> User | None:
        return (
            self.db.query(User)
            .filter(User.email == email)
            .first()
        )

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()

        return user