import uuid

from app.models.user import User
from app.services.user_service import UserService


def test_create_user_hashes_password(db_session):
    email = f"user-{uuid.uuid4()}@example.com"
    password = "secure-password-123"

    service = UserService(db_session)

    user = service.create_user(
        email=email,
        password=password,
    )

    assert user.id is not None
    assert user.email == email
    assert user.role == "landlord"
    assert user.is_active is True
    assert user.password_hash != password
    assert password not in user.password_hash


def test_create_user_rejects_duplicate_email(db_session):
    email = f"duplicate-{uuid.uuid4()}@example.com"

    service = UserService(db_session)

    service.create_user(
        email=email,
        password="secure-password-123",
    )

    try:
        service.create_user(
            email=email,
            password="another-password-456",
        )
        assert False, "Expected duplicate email error"
    except ValueError as exc:
        assert str(exc) == "User with this email already exists"


def test_create_user_supports_custom_role(db_session):
    email = f"custom-role-{uuid.uuid4()}@example.com"

    service = UserService(db_session)

    user = service.create_user(
        email=email,
        password="secure-password-123",
        role="admin",
    )

    assert user.role == "admin"


def test_created_user_password_can_be_verified(db_session):
    email = f"verify-{uuid.uuid4()}@example.com"
    password = "secure-password-123"

    service = UserService(db_session)

    user = service.create_user(
        email=email,
        password=password,
    )

    from app.core.security import verify_password

    assert verify_password(
        password,
        user.password_hash,
    ) is True

    assert verify_password(
        "wrong-password",
        user.password_hash,
    ) is False
