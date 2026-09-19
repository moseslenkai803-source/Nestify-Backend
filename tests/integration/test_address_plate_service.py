from app.services.address_plate_service import AddressPlateService


def test_create_plate_creates_unactivated_plate(db_session):
    service = AddressPlateService(db_session)

    plate = service.create_plate()

    assert plate.id is not None
    assert plate.plate_code.startswith("PLATE-")
    assert plate.status == "unactivated"
    assert plate.property_id is None
    assert plate.activated_at is None
    assert plate.verified_at is None


def test_get_plate_by_code_returns_existing_plate(db_session):
    service = AddressPlateService(db_session)

    created_plate = service.create_plate()

    found_plate = service.get_plate_by_code(
        created_plate.plate_code
    )

    assert found_plate is not None
    assert found_plate.id == created_plate.id
    assert found_plate.plate_code == created_plate.plate_code
