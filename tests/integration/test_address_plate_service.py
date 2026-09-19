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
