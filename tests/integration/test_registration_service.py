import uuid

from app.core.security import verify_password
from app.models.landlord import Landlord
from app.models.user import User
from app.services.registration_service import RegistrationService


def test_register_landlord_creates_user_and_landlord(db_session):
    email = f"register-{uuid.uuid4()}@example.com"
    password = "secure-password-123"

    service = RegistrationService(db_session)

    user, landlord = service.register_landlord(
        email=email,
        password=password,
        display_name="Registered Landlord",
        phone="+254700000000",
    )

    assert user.id is not None
    assert landlord.id is not None
    assert user.email == email
    assert user.role == "landlord"
    assert user.is_active is True
    assert landlord.user_id == user.id
    assert landlord.display_name == "Registered Landlord"
    assert landlord.phone == "+254700000000"
    assert landlord.landlord_type == "individual"


def test_register_landlord_hashes_password(db_session):
    email = f"hash-{uuid.uuid4()}@example.com"
    password = "secure-password-123"

    service = RegistrationService(db_session)

    user, _ = service.register_landlord(
        email=email,
        password=password,
        display_name="Hash Test Landlord",
        phone="+254711000000",
    )

    assert user.password_hash != password
    assert password not in user.password_hash
    assert verify_password(password, user.password_hash) is True
    assert verify_password("wrong-password", user.password_hash) is False


def test_register_landlord_links_user_and_landlord(db_session):
    email = f"link-{uuid.uuid4()}@example.com"

    service = RegistrationService(db_session)

    user, landlord = service.register_landlord(
        email=email,
        password="secure-password-123",
        display_name="Linked Landlord",
        phone="+254722000000",
    )

    stored_user = db_session.get(User, user.id)
    stored_landlord = db_session.get(Landlord, landlord.id)

    assert stored_user is not None
    assert stored_landlord is not None
    assert stored_landlord.user_id == stored_user.id


def test_register_landlord_rejects_duplicate_email(db_session):
    email = f"duplicate-register-{uuid.uuid4()}@example.com"

    service = RegistrationService(db_session)

    service.register_landlord(
        email=email,
        password="secure-password-123",
        display_name="First Landlord",
        phone="+254733000000",
    )

    try:
        service.register_landlord(
            email=email,
            password="another-password-456",
            display_name="Second Landlord",
            phone="+254744000000",
        )
        assert False, "Expected duplicate email error"
    except ValueError as exc:
        assert str(exc) == "User with this email already exists"
