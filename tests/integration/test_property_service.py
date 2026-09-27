import pytest
import uuid

from sqlalchemy.exc import IntegrityError

from app.models.landlord import Landlord
from app.models.property import Property
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


def test_database_rejects_invalid_property_status(db_session):
    user = User(
        email=f"status-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="landlord",
    )
    db_session.add(user)
    db_session.flush()

    landlord = Landlord(
        user_id=user.id,
        display_name="Status Test Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()

    property = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Invalid Status Property",
        property_type="residential",
        status="invalid_status",
    )
    db_session.add(property)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()
