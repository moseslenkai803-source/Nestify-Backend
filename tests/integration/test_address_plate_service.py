import uuid

import pytest

from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
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


def test_verify_plate_changes_status_and_sets_verified_at(db_session):
    service = AddressPlateService(db_session)

    plate = service.create_plate()

    verified_plate = service.verify_plate(
        plate.plate_code
    )

    assert verified_plate.id == plate.id
    assert verified_plate.status == "verified"
    assert verified_plate.verified_at is not None










def test_verified_plate_cannot_be_verified_again(db_session):
    service = AddressPlateService(db_session)

    plate = service.create_plate()

    service.verify_plate(plate.plate_code)

    with pytest.raises(
        ValueError,
        match="Plate cannot be verified in its current status",
    ):
        service.verify_plate(plate.plate_code)






