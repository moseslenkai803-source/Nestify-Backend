import uuid

from app.models.landlord import Landlord
from app.models.user import User
from app.repositories.landlord_repository import LandlordRepository


def test_get_by_id_returns_landlord(db_session):
    user = User(
        id=uuid.uuid4(),
        email="landlord-test@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )

    db_session.add(user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    repository = LandlordRepository(db_session)

    result = repository.get_by_id(landlord.id)

    assert result is not None
    assert result.id == landlord.id
    assert result.user_id == user.id
    assert result.display_name == "Test Landlord"


def test_get_by_user_id_returns_landlord(db_session):
    user = User(
        id=uuid.uuid4(),
        email="landlord-user-test@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="User Lookup Landlord",
        phone="+254711000000",
        landlord_type="individual",
    )

    db_session.add(user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    repository = LandlordRepository(db_session)

    result = repository.get_by_user_id(user.id)

    assert result is not None
    assert result.id == landlord.id
    assert result.user_id == user.id
    assert result.display_name == "User Lookup Landlord"


def test_add_persists_landlord(db_session):
    user = User(
        email="landlord-add@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Added Landlord",
        phone="+254722000000",
        landlord_type="individual",
    )

    repository = LandlordRepository(db_session)

    result = repository.add(landlord)

    assert result.id is not None
    assert result.user_id == user.id

    stored_landlord = db_session.get(
        Landlord,
        result.id,
    )

    assert stored_landlord is not None
    assert stored_landlord.display_name == "Added Landlord"
    assert stored_landlord.phone == "+254722000000"
