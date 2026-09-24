import uuid

import pytest

from app.models.building import Building
from app.models.floor import Floor
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.services.floor_service import FloorService


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
        display_name="Floor Service Landlord",
        phone="+254700000000",
        landlord_type="individual",
    )
    db_session.add(landlord)
    db_session.flush()
    return landlord


def create_property(
    db_session,
    landlord,
    *,
    name="Floor Service Property",
):
    property_record = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name=name,
        property_type="residential",
        status="draft",
    )
    db_session.add(property_record)
    db_session.flush()
    return property_record


def create_building(
    db_session,
    property_record,
    *,
    building_number="1",
    name="Main Building",
):
    building = Building(
        property_id=property_record.id,
        building_number=building_number,
        name=name,
        status="draft",
    )
    db_session.add(building)
    db_session.flush()
    return building


def create_floor(
    db_session,
    building,
    *,
    floor_number="1",
    name="First Floor",
    status="draft",
):
    floor = Floor(
        building_id=building.id,
        floor_number=floor_number,
        name=name,
        status=status,
    )
    db_session.add(floor)
    db_session.flush()
    return floor


def test_create_floor_creates_draft_floor(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)

    service = FloorService(db_session)

    floor = service.create_floor(
        user=user,
        property_id=property_record.id,
        building_id=building.id,
        floor_number="1",
        name="First Floor",
    )

    assert floor.id is not None
    assert floor.building_id == building.id
    assert floor.floor_number == "1"
    assert floor.name == "First Floor"
    assert floor.status == "draft"


def test_create_floor_rejects_unauthorized_user(db_session):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)

    other_user = create_user(db_session)

    service = FloorService(db_session)

    with pytest.raises(
        ValueError,
        match="User is not authorized for this property",
    ):
        service.create_floor(
            user=other_user,
            property_id=property_record.id,
            building_id=building.id,
            floor_number="1",
            name="Unauthorized Floor",
        )


def test_create_floor_rejects_building_from_wrong_property(
    db_session,
):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)

    property_one = create_property(
        db_session,
        landlord,
        name="Property One",
    )
    property_two = create_property(
        db_session,
        landlord,
        name="Property Two",
    )

    building = create_building(
        db_session,
        property_one,
    )

    service = FloorService(db_session)

    with pytest.raises(ValueError, match="Building not found"):
        service.create_floor(
            user=user,
            property_id=property_two.id,
            building_id=building.id,
            floor_number="1",
            name="Wrong Parent Floor",
        )


def test_get_floor_returns_floor(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)

    service = FloorService(db_session)

    result = service.get_floor(
        user=user,
        property_id=property_record.id,
        floor_id=floor.id,
    )

    assert result.id == floor.id
    assert result.building_id == building.id
    assert result.floor_number == "1"


def test_get_floor_raises_when_floor_does_not_exist(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)

    service = FloorService(db_session)

    with pytest.raises(ValueError, match="Floor not found"):
        service.get_floor(
            user=user,
            property_id=property_record.id,
            floor_id=uuid.uuid4(),
        )


def test_get_floor_rejects_wrong_parent_property(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)

    property_one = create_property(
        db_session,
        landlord,
        name="Property One",
    )
    property_two = create_property(
        db_session,
        landlord,
        name="Property Two",
    )

    building = create_building(
        db_session,
        property_one,
    )
    floor = create_floor(db_session, building)

    service = FloorService(db_session)

    with pytest.raises(ValueError, match="Floor not found"):
        service.get_floor(
            user=user,
            property_id=property_two.id,
            floor_id=floor.id,
        )


def test_list_floors_returns_building_floors_for_authorized_user(
    db_session,
):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)

    floor_one = create_floor(
        db_session,
        building,
        floor_number="1",
        name="Ground Floor",
    )
    floor_two = create_floor(
        db_session,
        building,
        floor_number="2",
        name="First Floor",
        status="active",
    )

    service = FloorService(db_session)

    result = service.list_floors(
        user=user,
        property_id=property_record.id,
        building_id=building.id,
    )

    assert len(result) == 2
    assert {floor.id for floor in result} == {
        floor_one.id,
        floor_two.id,
    }


def test_list_floors_rejects_unauthorized_user(db_session):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)

    other_user = create_user(db_session)

    service = FloorService(db_session)

    with pytest.raises(
        ValueError,
        match="User is not authorized for this property",
    ):
        service.list_floors(
            user=other_user,
            property_id=property_record.id,
            building_id=building.id,
        )


def test_list_floors_rejects_building_from_wrong_property(
    db_session,
):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)

    property_one = create_property(
        db_session,
        landlord,
        name="Property One",
    )
    property_two = create_property(
        db_session,
        landlord,
        name="Property Two",
    )

    building = create_building(
        db_session,
        property_one,
    )

    service = FloorService(db_session)

    with pytest.raises(ValueError, match="Building not found"):
        service.list_floors(
            user=user,
            property_id=property_two.id,
            building_id=building.id,
        )
