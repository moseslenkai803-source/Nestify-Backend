import uuid

import pytest

from app.models.building import Building
from app.models.floor import Floor
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.space import Space
from app.models.user import User
from app.services.space_service import SpaceService


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
        display_name="Space Service Landlord",
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
    name="Space Service Property",
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


def create_space(
    db_session,
    floor,
    *,
    space_number="101",
    name="Apartment 101",
    space_type="residential",
    status="draft",
):
    space = Space(
        floor_id=floor.id,
        space_number=space_number,
        name=name,
        space_type=space_type,
        status=status,
    )
    db_session.add(space)
    db_session.flush()
    return space


def test_create_space_creates_draft_space(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)

    service = SpaceService(db_session)

    space = service.create_space(
        user=user,
        property_id=property_record.id,
        building_id=building.id,
        floor_id=floor.id,
        space_number="101",
        name="Apartment 101",
        space_type="residential",
    )

    assert space.id is not None
    assert space.floor_id == floor.id
    assert space.space_number == "101"
    assert space.name == "Apartment 101"
    assert space.space_type == "residential"
    assert space.status == "draft"


def test_create_space_rejects_unauthorized_user(db_session):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)

    other_user = create_user(db_session)

    service = SpaceService(db_session)

    with pytest.raises(
        ValueError,
        match="User is not authorized for this property",
    ):
        service.create_space(
            user=other_user,
            property_id=property_record.id,
            building_id=building.id,
            floor_id=floor.id,
            space_number="101",
            name="Unauthorized Space",
        )


def test_create_space_rejects_building_from_wrong_property(
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
    floor = create_floor(db_session, building)

    service = SpaceService(db_session)

    with pytest.raises(ValueError, match="Building not found"):
        service.create_space(
            user=user,
            property_id=property_two.id,
            building_id=building.id,
            floor_id=floor.id,
            space_number="101",
            name="Wrong Parent Space",
        )


def test_create_space_rejects_floor_from_wrong_building(
    db_session,
):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)

    building_one = create_building(
        db_session,
        property_record,
        building_number="1",
        name="Building One",
    )
    building_two = create_building(
        db_session,
        property_record,
        building_number="2",
        name="Building Two",
    )

    floor = create_floor(db_session, building_one)

    service = SpaceService(db_session)

    with pytest.raises(ValueError, match="Floor not found"):
        service.create_space(
            user=user,
            property_id=property_record.id,
            building_id=building_two.id,
            floor_id=floor.id,
            space_number="101",
            name="Wrong Building Space",
        )


def test_create_space_rejects_nonexistent_floor(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)

    service = SpaceService(db_session)

    with pytest.raises(ValueError, match="Floor not found"):
        service.create_space(
            user=user,
            property_id=property_record.id,
            building_id=building.id,
            floor_id=uuid.uuid4(),
            space_number="101",
            name="Missing Floor Space",
        )


def test_get_space_returns_space(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)
    space = create_space(db_session, floor)

    service = SpaceService(db_session)

    result = service.get_space(
        user=user,
        property_id=property_record.id,
        building_id=building.id,
        floor_id=floor.id,
        space_id=space.id,
    )

    assert result.id == space.id
    assert result.floor_id == floor.id
    assert result.space_number == "101"
    assert result.space_type == "residential"


def test_get_space_raises_when_space_does_not_exist(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)

    service = SpaceService(db_session)

    with pytest.raises(ValueError, match="Space not found"):
        service.get_space(
            user=user,
            property_id=property_record.id,
            building_id=building.id,
            floor_id=floor.id,
            space_id=uuid.uuid4(),
        )


def test_get_space_rejects_wrong_parent_floor(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)

    floor_one = create_floor(
        db_session,
        building,
        floor_number="1",
        name="Floor One",
    )
    floor_two = create_floor(
        db_session,
        building,
        floor_number="2",
        name="Floor Two",
    )

    space = create_space(
        db_session,
        floor_one,
    )

    service = SpaceService(db_session)

    with pytest.raises(ValueError, match="Space not found"):
        service.get_space(
            user=user,
            property_id=property_record.id,
            building_id=building.id,
            floor_id=floor_two.id,
            space_id=space.id,
        )


def test_get_space_rejects_wrong_parent_building(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)

    building_one = create_building(
        db_session,
        property_record,
        building_number="1",
        name="Building One",
    )
    building_two = create_building(
        db_session,
        property_record,
        building_number="2",
        name="Building Two",
    )

    floor = create_floor(db_session, building_one)
    space = create_space(db_session, floor)

    service = SpaceService(db_session)

    with pytest.raises(ValueError, match="Space not found"):
        service.get_space(
            user=user,
            property_id=property_record.id,
            building_id=building_two.id,
            floor_id=floor.id,
            space_id=space.id,
        )


def test_get_space_rejects_wrong_parent_property(db_session):
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

    building = create_building(db_session, property_one)
    floor = create_floor(db_session, building)
    space = create_space(db_session, floor)

    service = SpaceService(db_session)

    with pytest.raises(ValueError, match="Space not found"):
        service.get_space(
            user=user,
            property_id=property_two.id,
            building_id=building.id,
            floor_id=floor.id,
            space_id=space.id,
        )


def test_list_spaces_returns_floor_spaces_for_authorized_user(
    db_session,
):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)

    space_one = create_space(
        db_session,
        floor,
        space_number="101",
        name="Apartment 101",
    )
    space_two = create_space(
        db_session,
        floor,
        space_number="102",
        name="Apartment 102",
        status="active",
    )

    service = SpaceService(db_session)

    result = service.list_spaces(
        user=user,
        property_id=property_record.id,
        building_id=building.id,
        floor_id=floor.id,
    )

    assert len(result) == 2
    assert {space.id for space in result} == {
        space_one.id,
        space_two.id,
    }


def test_list_spaces_rejects_unauthorized_user(db_session):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)

    other_user = create_user(db_session)

    service = SpaceService(db_session)

    with pytest.raises(
        ValueError,
        match="User is not authorized for this property",
    ):
        service.list_spaces(
            user=other_user,
            property_id=property_record.id,
            building_id=building.id,
            floor_id=floor.id,
        )


def test_list_spaces_rejects_building_from_wrong_property(
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
    floor = create_floor(db_session, building)

    service = SpaceService(db_session)

    with pytest.raises(ValueError, match="Building not found"):
        service.list_spaces(
            user=user,
            property_id=property_two.id,
            building_id=building.id,
            floor_id=floor.id,
        )


def test_list_spaces_rejects_floor_from_wrong_building(
    db_session,
):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)

    building_one = create_building(
        db_session,
        property_record,
        building_number="1",
        name="Building One",
    )
    building_two = create_building(
        db_session,
        property_record,
        building_number="2",
        name="Building Two",
    )

    floor = create_floor(db_session, building_one)

    service = SpaceService(db_session)

    with pytest.raises(ValueError, match="Floor not found"):
        service.list_spaces(
            user=user,
            property_id=property_record.id,
            building_id=building_two.id,
            floor_id=floor.id,
        )


def test_duplicate_space_number_within_floor_is_rejected(db_session):
    from sqlalchemy.exc import IntegrityError

    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)

    first_space = Space(
        floor_id=floor.id,
        space_number="A-101",
        name="First Space",
        space_type="apartment",
        status="draft",
    )

    db_session.add(first_space)
    db_session.flush()

    duplicate_space = Space(
        floor_id=floor.id,
        space_number="A-101",
        name="Duplicate Space",
        space_type="apartment",
        status="draft",
    )

    db_session.add(duplicate_space)

    try:
        db_session.flush()
    except IntegrityError:
        db_session.rollback()
    else:
        raise AssertionError(
            "Duplicate space number should violate the floor-scoped "
            "unique constraint"
        )
