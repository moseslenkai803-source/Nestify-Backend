import uuid

from app.models.building import Building
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.repositories.building_repository import BuildingRepository


def create_property(db_session, email, property_code):
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash="hashed-password",
        role="landlord",
        is_active=True,
    )

    landlord = Landlord(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name="Building Test Landlord",
        phone="+254700000001",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=property_code,
        name="Building Test Property",
        property_type="residential",
        status="draft",
    )

    db_session.add(user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    return property_record


def test_get_by_id_returns_building(db_session):
    property_record = create_property(
        db_session,
        "building-get-id@example.com",
        "NEST-BUILDING-001",
    )

    building = Building(
        id=uuid.uuid4(),
        property_id=property_record.id,
        building_number="1",
        name="Main Building",
        status="draft",
    )

    db_session.add(building)
    db_session.flush()

    repository = BuildingRepository(db_session)

    result = repository.get_by_id(building.id)

    assert result is not None
    assert result.id == building.id
    assert result.property_id == property_record.id
    assert result.building_number == "1"
    assert result.name == "Main Building"
    assert result.status == "draft"


def test_get_by_property_id_returns_property_buildings(db_session):
    property_record = create_property(
        db_session,
        "building-list@example.com",
        "NEST-BUILDING-002",
    )

    building_one = Building(
        id=uuid.uuid4(),
        property_id=property_record.id,
        building_number="1",
        name="Building One",
        status="draft",
    )

    building_two = Building(
        id=uuid.uuid4(),
        property_id=property_record.id,
        building_number="2",
        name="Building Two",
        status="active",
    )

    db_session.add_all([building_one, building_two])
    db_session.flush()

    repository = BuildingRepository(db_session)

    result = repository.get_by_property_id(property_record.id)

    assert len(result) == 2
    assert {building.id for building in result} == {
        building_one.id,
        building_two.id,
    }


def test_get_by_property_and_number_returns_matching_building(db_session):
    property_record = create_property(
        db_session,
        "building-number@example.com",
        "NEST-BUILDING-003",
    )

    building = Building(
        id=uuid.uuid4(),
        property_id=property_record.id,
        building_number="A",
        name="Block A",
        status="draft",
    )

    db_session.add(building)
    db_session.flush()

    repository = BuildingRepository(db_session)

    result = repository.get_by_property_and_number(
        property_record.id,
        "A",
    )

    assert result is not None
    assert result.id == building.id
    assert result.building_number == "A"


def test_add_persists_building(db_session):
    property_record = create_property(
        db_session,
        "building-add@example.com",
        "NEST-BUILDING-004",
    )

    building = Building(
        property_id=property_record.id,
        building_number="3",
        name="Added Building",
        status="draft",
    )

    repository = BuildingRepository(db_session)

    result = repository.add(building)

    assert result is building
    assert result.id is not None
    assert result.property_id == property_record.id
    assert result.building_number == "3"

    stored_building = repository.get_by_id(result.id)

    assert stored_building is not None
    assert stored_building.id == result.id
    assert stored_building.name == "Added Building"


def test_duplicate_building_number_within_property_is_rejected(db_session):
    from sqlalchemy.exc import IntegrityError

    property_record = create_property(
        db_session,
        "building-unique@example.com",
        "NEST-BUILDING-005",
    )

    first_building = Building(
        property_id=property_record.id,
        building_number="1",
        name="First Building",
        status="draft",
    )

    db_session.add(first_building)
    db_session.flush()

    duplicate_building = Building(
        property_id=property_record.id,
        building_number="1",
        name="Duplicate Building",
        status="draft",
    )

    db_session.add(duplicate_building)

    try:
        db_session.flush()
    except IntegrityError:
        db_session.rollback()
    else:
        raise AssertionError(
            "Duplicate building number should violate the property-scoped "
            "unique constraint"
        )
