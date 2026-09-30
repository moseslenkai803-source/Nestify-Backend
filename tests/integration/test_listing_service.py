import uuid

import pytest

from app.models.building import Building
from app.models.floor import Floor
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.property_access import PropertyAccess
from app.models.space import Space
from app.models.user import User
from app.services.listing_service import ListingService


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
        display_name="Listing Service Landlord",
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
    name="Listing Service Property",
    status="draft",
):
    property_record = Property(
        landlord_id=landlord.id,
        property_code=f"NEST-{uuid.uuid4().hex[:12].upper()}",
        name=name,
        property_type="residential",
        status=status,
    )
    db_session.add(property_record)
    db_session.flush()
    return property_record


def create_building(
    db_session,
    property_record,
    *,
    building_number="1",
):
    building = Building(
        property_id=property_record.id,
        building_number=building_number,
        name="Main Building",
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
):
    floor = Floor(
        building_id=building.id,
        floor_number=floor_number,
        name="First Floor",
        status="draft",
    )
    db_session.add(floor)
    db_session.flush()
    return floor


def create_space(
    db_session,
    floor,
    *,
    space_number="101",
):
    space = Space(
        floor_id=floor.id,
        space_number=space_number,
        name="Space 101",
        space_type="residential",
        status="draft",
    )
    db_session.add(space)
    db_session.flush()
    return space


def grant_property_management_access(
    db_session,
    user,
    property_record,
):
    access = PropertyAccess(
        user_id=user.id,
        property_id=property_record.id,
        access_type="property_management",
    )
    db_session.add(access)
    db_session.flush()
    return access


def test_create_property_listing_creates_draft(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)

    service = ListingService(db_session)

    listing = service.create_property_listing(
        user=user,
        property_id=property_record.id,
        transaction_type="rent",
        title="House for Rent",
        description="A residential property",
    )

    assert listing.id is not None
    assert listing.property_id == property_record.id
    assert listing.floor_id is None
    assert listing.space_id is None
    assert listing.transaction_type == "rent"
    assert listing.title == "House for Rent"
    assert listing.description == "A residential property"
    assert listing.status == "draft"
    assert listing.published_at is None


def test_create_floor_listing_creates_draft(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)

    service = ListingService(db_session)

    listing = service.create_floor_listing(
        user=user,
        property_id=property_record.id,
        floor_id=floor.id,
        transaction_type="sale",
        title="First Floor for Sale",
    )

    assert listing.id is not None
    assert listing.property_id is None
    assert listing.floor_id == floor.id
    assert listing.space_id is None
    assert listing.transaction_type == "sale"
    assert listing.status == "draft"


def test_create_space_listing_creates_draft(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)
    space = create_space(db_session, floor)

    service = ListingService(db_session)

    listing = service.create_space_listing(
        user=user,
        property_id=property_record.id,
        building_id=building.id,
        floor_id=floor.id,
        space_id=space.id,
        transaction_type="rent",
        title="Space 101 for Rent",
    )

    assert listing.id is not None
    assert listing.property_id is None
    assert listing.floor_id is None
    assert listing.space_id == space.id
    assert listing.transaction_type == "rent"
    assert listing.status == "draft"


def test_create_listing_rejects_invalid_transaction_type(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)

    service = ListingService(db_session)

    with pytest.raises(ValueError, match="Invalid transaction type"):
        service.create_property_listing(
            user=user,
            property_id=property_record.id,
            transaction_type="lease",
            title="Invalid Listing",
        )


def test_create_listing_rejects_unauthorized_user(db_session):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property_record = create_property(db_session, landlord)

    other_user = create_user(db_session)

    service = ListingService(db_session)

    with pytest.raises(
        ValueError,
        match="User is not authorized for this property",
    ):
        service.create_property_listing(
            user=other_user,
            property_id=property_record.id,
            transaction_type="rent",
            title="Unauthorized Listing",
        )


def test_create_floor_listing_rejects_floor_from_wrong_property(
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

    building = create_building(db_session, property_one)
    floor = create_floor(db_session, building)

    service = ListingService(db_session)

    with pytest.raises(ValueError, match="Floor not found"):
        service.create_floor_listing(
            user=user,
            property_id=property_two.id,
            floor_id=floor.id,
            transaction_type="rent",
            title="Wrong Property Floor",
        )


def test_create_space_listing_rejects_space_from_wrong_building(
    db_session,
):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)

    building_one = create_building(
        db_session,
        property_record,
        building_number="1",
    )
    building_two = create_building(
        db_session,
        property_record,
        building_number="2",
    )

    floor = create_floor(db_session, building_one)
    space = create_space(db_session, floor)

    service = ListingService(db_session)

    with pytest.raises(ValueError, match="Space not found"):
        service.create_space_listing(
            user=user,
            property_id=property_record.id,
            building_id=building_two.id,
            floor_id=floor.id,
            space_id=space.id,
            transaction_type="rent",
            title="Wrong Building Space",
        )


def test_publish_listing_rejects_inactive_property(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(
        db_session,
        landlord,
        status="verified",
    )

    service = ListingService(db_session)

    listing = service.create_property_listing(
        user=user,
        property_id=property_record.id,
        transaction_type="rent",
        title="Verified Property",
    )

    with pytest.raises(
        ValueError,
        match="Property must be active before listing can be published",
    ):
        service.publish_listing(
            user=user,
            listing_id=listing.id,
        )


def test_publish_property_listing_sets_published_state(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(
        db_session,
        landlord,
        status="active",
    )

    service = ListingService(db_session)

    listing = service.create_property_listing(
        user=user,
        property_id=property_record.id,
        transaction_type="rent",
        title="Active Property",
    )

    result = service.publish_listing(
        user=user,
        listing_id=listing.id,
    )

    assert result.status == "published"
    assert result.published_at is not None


def test_publish_floor_listing_resolves_owning_property(
    db_session,
):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(
        db_session,
        landlord,
        status="active",
    )
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)

    service = ListingService(db_session)

    listing = service.create_floor_listing(
        user=user,
        property_id=property_record.id,
        floor_id=floor.id,
        transaction_type="rent",
        title="Active Floor",
    )

    result = service.publish_listing(
        user=user,
        listing_id=listing.id,
    )

    assert result.status == "published"
    assert result.published_at is not None


def test_publish_space_listing_resolves_owning_property(
    db_session,
):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(
        db_session,
        landlord,
        status="active",
    )
    building = create_building(db_session, property_record)
    floor = create_floor(db_session, building)
    space = create_space(db_session, floor)

    service = ListingService(db_session)

    listing = service.create_space_listing(
        user=user,
        property_id=property_record.id,
        building_id=building.id,
        floor_id=floor.id,
        space_id=space.id,
        transaction_type="rent",
        title="Active Space",
    )

    result = service.publish_listing(
        user=user,
        listing_id=listing.id,
    )

    assert result.status == "published"
    assert result.published_at is not None


def test_publish_listing_rejects_already_published_listing(
    db_session,
):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(
        db_session,
        landlord,
        status="active",
    )

    service = ListingService(db_session)

    listing = service.create_property_listing(
        user=user,
        property_id=property_record.id,
        transaction_type="rent",
        title="Already Published",
    )

    service.publish_listing(
        user=user,
        listing_id=listing.id,
    )

    with pytest.raises(
        ValueError,
        match="Listing is already published",
    ):
        service.publish_listing(
            user=user,
            listing_id=listing.id,
        )


def test_unpublish_listing_sets_unpublished_state(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(
        db_session,
        landlord,
        status="active",
    )

    service = ListingService(db_session)

    listing = service.create_property_listing(
        user=user,
        property_id=property_record.id,
        transaction_type="rent",
        title="Unpublish Test",
    )

    service.publish_listing(
        user=user,
        listing_id=listing.id,
    )

    result = service.unpublish_listing(
        user=user,
        listing_id=listing.id,
    )

    assert result.status == "unpublished"
    assert result.published_at is None


def test_unpublish_listing_rejects_draft(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(db_session, landlord)

    service = ListingService(db_session)

    listing = service.create_property_listing(
        user=user,
        property_id=property_record.id,
        transaction_type="rent",
        title="Draft Listing",
    )

    with pytest.raises(
        ValueError,
        match="Listing is not published",
    ):
        service.unpublish_listing(
            user=user,
            listing_id=listing.id,
        )


def test_unpublished_listing_can_be_republished(db_session):
    user = create_user(db_session)
    landlord = create_landlord(db_session, user)
    property_record = create_property(
        db_session,
        landlord,
        status="active",
    )

    service = ListingService(db_session)

    listing = service.create_property_listing(
        user=user,
        property_id=property_record.id,
        transaction_type="rent",
        title="Republish Test",
    )

    service.publish_listing(
        user=user,
        listing_id=listing.id,
    )
    service.unpublish_listing(
        user=user,
        listing_id=listing.id,
    )

    result = service.publish_listing(
        user=user,
        listing_id=listing.id,
    )

    assert result.status == "published"
    assert result.published_at is not None


def test_property_manager_can_create_and_publish_listing(db_session):
    owner = create_user(db_session)
    landlord = create_landlord(db_session, owner)
    property_record = create_property(
        db_session,
        landlord,
        status="active",
    )

    manager = create_user(db_session, role="property_manager")

    grant_property_management_access(
        db_session,
        manager,
        property_record,
    )

    service = ListingService(db_session)

    listing = service.create_property_listing(
        user=manager,
        property_id=property_record.id,
        transaction_type="rent",
        title="Manager Listing",
    )

    result = service.publish_listing(
        user=manager,
        listing_id=listing.id,
    )

    assert result.status == "published"
    assert result.property_id == property_record.id
