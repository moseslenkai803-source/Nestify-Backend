import uuid

from app.models.address_plate import AddressPlate
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
