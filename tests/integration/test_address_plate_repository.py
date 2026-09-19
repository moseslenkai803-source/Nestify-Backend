import uuid

from app.models.address_plate import AddressPlate
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.repositories.address_plate_repository import AddressPlateRepository


def test_get_by_plate_code_returns_address_plate(db_session):
    plate = AddressPlate(
        id=uuid.uuid4(),
        plate_code="NEST-PLATE-001",
        status="unactivated",
    )

    db_session.add(plate)
    db_session.flush()

    repository = AddressPlateRepository(db_session)

    result = repository.get_by_plate_code("NEST-PLATE-001")

    assert result is not None
    assert result.id == plate.id
    assert result.plate_code == "NEST-PLATE-001"
    assert result.status == "unactivated"
    assert result.property_id is None


def test_get_by_property_id_returns_address_plate(db_session):
    user = User(
        id=uuid.uuid4(),
        email="plate-property-test@example.com",
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Plate Property Test Landlord",
        phone="+254700000002",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code="NEST-PLATE-PROP-001",
        name="Plate Property Test",
        property_type="residential",
        status="draft",
    )

    plate = AddressPlate(
        id=uuid.uuid4(),
        property_id=property_record.id,
        plate_code="NEST-PLATE-002",
        status="active",
    )

    db_session.add(user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    db_session.add(plate)
    db_session.flush()

    repository = AddressPlateRepository(db_session)

    result = repository.get_by_property_id(property_record.id)

    assert result is not None
    assert result.id == plate.id
    assert result.property_id == property_record.id
    assert result.plate_code == "NEST-PLATE-002"
    assert result.status == "active"
