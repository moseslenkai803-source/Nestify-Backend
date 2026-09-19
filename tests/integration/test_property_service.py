import pytest
import uuid

from app.models.landlord import Landlord
from app.models.user import User
from app.services.property_service import PropertyService


def test_create_property_creates_draft_property(db_session):
    user = User(
        email=f"service-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Service Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    service = PropertyService(db_session)

    property = service.create_property(
        landlord_id=landlord.id,
        name="Service Test Property",
        property_type="residential",
    )

    assert property.id is not None
    assert property.landlord_id == landlord.id
    assert property.name == "Service Test Property"
    assert property.property_type == "residential"
    assert property.status == "draft"
    assert property.property_code.startswith("NEST-")


def test_create_property_raises_when_landlord_does_not_exist(db_session):
    service = PropertyService(db_session)

    with pytest.raises(ValueError, match="Landlord not found"):
        service.create_property(
            landlord_id=uuid.uuid4(),
            name="Invalid Landlord Property",
            property_type="residential",
        )
