import uuid

from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.repositories.property_repository import PropertyRepository


def test_get_by_id_returns_property(db_session):
    user = User(
        id=uuid.uuid4(),
        email="property-test@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Property Test Landlord",
        phone="+254700000001",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code="NEST-TEST-001",
        name="Test Property",
        property_type="residential",
        status="draft",
    )

    db_session.add(user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    repository = PropertyRepository(db_session)

    result = repository.get_by_id(property_record.id)

    assert result is not None
    assert result.id == property_record.id
    assert result.landlord_id == landlord.id
    assert result.property_code == "NEST-TEST-001"
    assert result.name == "Test Property"
    assert result.property_type == "residential"
    assert result.status == "draft"
