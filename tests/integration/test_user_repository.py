import uuid

from app.models.user import User
from app.repositories.user_repository import UserRepository


def test_get_by_id_returns_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    repository = UserRepository(db_session)

    result = repository.get_by_id(user.id)

    assert result is not None
    assert result.id == user.id
    assert result.email == "test@example.com"


def test_get_by_email_returns_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email="email-lookup@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    repository = UserRepository(db_session)

    result = repository.get_by_email(
        "email-lookup@example.com"
    )

    assert result is not None
    assert result.id == user.id
    assert result.email == "email-lookup@example.com"


def test_add_persists_user(db_session):
    user = User(
        email="repository-add@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    repository = UserRepository(db_session)

    result = repository.add(user)

    assert result.id is not None

    stored_user = db_session.get(User, result.id)

    assert stored_user is not None
    assert stored_user.email == "repository-add@example.com"