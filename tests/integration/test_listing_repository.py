import uuid

from app.models.building import Building
from app.models.floor import Floor
from app.models.landlord import Landlord
from app.models.listing import Listing
from app.models.property import Property
from app.models.space import Space
from app.models.user import User
from app.repositories.listing_repository import ListingRepository


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
        display_name="Listing Test Landlord",
        phone="+254700000001",
        landlord_type="individual",
    )

    property_record = Property(
        id=uuid.uuid4(),
        landlord_id=landlord.id,
        property_code=property_code,
        name="Listing Test Property",
        property_type="residential",
        status="active",
    )

    db_session.add(user)
    db_session.flush()

    db_session.add(landlord)
    db_session.flush()

    db_session.add(property_record)
    db_session.flush()

    return property_record


def create_hierarchy(db_session, email, property_code):
    property_record = create_property(
        db_session,
        email,
        property_code,
    )

    building = Building(
        id=uuid.uuid4(),
        property_id=property_record.id,
        building_number="1",
        name="Main Building",
        status="active",
    )

    db_session.add(building)
    db_session.flush()

    floor = Floor(
        id=uuid.uuid4(),
        building_id=building.id,
        floor_number="1",
        name="First Floor",
        status="active",
    )

    db_session.add(floor)
    db_session.flush()

    space = Space(
        id=uuid.uuid4(),
        floor_id=floor.id,
        space_number="101",
        name="Office 101",
        space_type="office",
        status="active",
    )

    db_session.add(space)
    db_session.flush()

    return property_record, building, floor, space


def test_get_by_id_returns_listing(db_session):
    property_record = create_property(
        db_session,
        "listing-get-id@example.com",
        "NEST-LISTING-001",
    )

    listing = Listing(
        id=uuid.uuid4(),
        property_id=property_record.id,
        transaction_type="sale",
        title="Property For Sale",
        description="Test property listing",
        status="draft",
    )

    db_session.add(listing)
    db_session.flush()

    repository = ListingRepository(db_session)

    result = repository.get_by_id(listing.id)

    assert result is not None
    assert result.id == listing.id
    assert result.property_id == property_record.id
    assert result.transaction_type == "sale"
    assert result.title == "Property For Sale"
    assert result.status == "draft"


def test_get_by_id_for_update_returns_listing(db_session):
    property_record = create_property(
        db_session,
        "listing-lock@example.com",
        "NEST-LISTING-002",
    )

    listing = Listing(
        property_id=property_record.id,
        transaction_type="rent",
        title="Property For Rent",
        status="draft",
    )

    db_session.add(listing)
    db_session.flush()

    repository = ListingRepository(db_session)

    result = repository.get_by_id_for_update(listing.id)

    assert result is not None
    assert result.id == listing.id
    assert result.property_id == property_record.id


def test_get_by_property_id_returns_property_listings(db_session):
    property_record = create_property(
        db_session,
        "listing-property@example.com",
        "NEST-LISTING-003",
    )

    listing_one = Listing(
        property_id=property_record.id,
        transaction_type="sale",
        title="Whole Property Sale",
        status="draft",
    )

    listing_two = Listing(
        property_id=property_record.id,
        transaction_type="rent",
        title="Whole Property Rent",
        status="published",
    )

    db_session.add_all([listing_one, listing_two])
    db_session.flush()

    repository = ListingRepository(db_session)

    result = repository.get_by_property_id(property_record.id)

    assert len(result) == 2
    assert {listing.id for listing in result} == {
        listing_one.id,
        listing_two.id,
    }


def test_get_by_floor_id_returns_floor_listings(db_session):
    _, _, floor, _ = create_hierarchy(
        db_session,
        "listing-floor@example.com",
        "NEST-LISTING-004",
    )

    listing_one = Listing(
        floor_id=floor.id,
        transaction_type="rent",
        title="Floor Listing One",
        status="draft",
    )

    listing_two = Listing(
        floor_id=floor.id,
        transaction_type="sale",
        title="Floor Listing Two",
        status="unpublished",
    )

    db_session.add_all([listing_one, listing_two])
    db_session.flush()

    repository = ListingRepository(db_session)

    result = repository.get_by_floor_id(floor.id)

    assert len(result) == 2
    assert {listing.id for listing in result} == {
        listing_one.id,
        listing_two.id,
    }


def test_get_by_space_id_returns_space_listings(db_session):
    _, _, _, space = create_hierarchy(
        db_session,
        "listing-space@example.com",
        "NEST-LISTING-005",
    )

    listing_one = Listing(
        space_id=space.id,
        transaction_type="rent",
        title="Space Listing One",
        status="draft",
    )

    listing_two = Listing(
        space_id=space.id,
        transaction_type="rent",
        title="Space Listing Two",
        status="published",
    )

    db_session.add_all([listing_one, listing_two])
    db_session.flush()

    repository = ListingRepository(db_session)

    result = repository.get_by_space_id(space.id)

    assert len(result) == 2
    assert {listing.id for listing in result} == {
        listing_one.id,
        listing_two.id,
    }


def test_add_persists_listing(db_session):
    property_record = create_property(
        db_session,
        "listing-add@example.com",
        "NEST-LISTING-006",
    )

    listing = Listing(
        property_id=property_record.id,
        transaction_type="rent",
        title="Added Listing",
        description="Added through repository",
        status="draft",
    )

    repository = ListingRepository(db_session)

    result = repository.add(listing)

    assert result is listing
    assert result.id is not None
    assert result.property_id == property_record.id
    assert result.title == "Added Listing"

    stored_listing = repository.get_by_id(result.id)

    assert stored_listing is not None
    assert stored_listing.id == result.id
    assert stored_listing.transaction_type == "rent"
    assert stored_listing.status == "draft"
