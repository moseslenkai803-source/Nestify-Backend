import uuid

import pytest

from app.models.building import Building
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.building_service import BuildingService


def create_user(
    db_session,
    *,
    role="landlord",
    is_active=True,
):
    user = User(
        email=f"{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.flush()
    return user


def create_landlord(db_session, user):
    landlord = Landlord(
        user_id=user.id,
        display_name="Building Service Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()
    return landlord


def create_property(db_session, landlord):
    property_record = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name="Building Service Property",
        property_type="residential",
        status="draft",
    )
    db_session.add(property_record)
    db_session.flush()
    return property_record


def test_create_building_creates_draft_building(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)

    service = BuildingService(db_session)

    building = service.create_building(
        user=user,
        property_id=property_record.id,
        building_number="1",
        name="Main Building",
    )

    assert building.id is not None
    assert building.property_id == property_record.id
    assert building.building_number == "1"
    assert building.name == "Main Building"
    assert building.status == "draft"


def test_create_building_rejects_unauthorized_user(db_session):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property_record = create_property(db_session, landlord)

    other_user = create_user(db_session)

    service = BuildingService(db_session)

    with pytest.raises(
        ValueError,
        match="User is not authorized for this property",
    ):
        service.create_building(
            user=other_user,
            property_id=property_record.id,
            building_number="1",
            name="Unauthorized Building",
        )


def test_get_building_returns_building(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)

    building = Building(
        property_id=property_record.id,
        building_number="1",
        name="Main Building",
        status="draft",
    )
    db_session.add(building)
    db_session.flush()

    service = BuildingService(db_session)

    result = service.get_building(
        building_id=building.id,
    )

    assert result.id == building.id
    assert result.property_id == property_record.id
    assert result.building_number == "1"


def test_get_building_raises_when_building_does_not_exist(db_session):
    service = BuildingService(db_session)

    with pytest.raises(ValueError, match="Building not found"):
        service.get_building(
            building_id=uuid.uuid4(),
        )


def test_list_buildings_returns_property_buildings_for_authorized_user(
    db_session,
):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)

    building_one = Building(
        property_id=property_record.id,
        building_number="1",
        name="Building One",
        status="draft",
    )

    building_two = Building(
        property_id=property_record.id,
        building_number="2",
        name="Building Two",
        status="active",
    )

    db_session.add_all([building_one, building_two])
    db_session.flush()

    service = BuildingService(db_session)

    result = service.list_buildings(
        user=user,
        property_id=property_record.id,
    )

    assert len(result) == 2
    assert {building.id for building in result} == {
        building_one.id,
        building_two.id,
    }


def test_list_buildings_rejects_unauthorized_user(db_session):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property_record = create_property(db_session, landlord)

    other_user = create_user(db_session)

    service = BuildingService(db_session)

    with pytest.raises(
        ValueError,
        match="User is not authorized for this property",
    ):
        service.list_buildings(
            user=other_user,
            property_id=property_record.id,
        )
