from uuid import uuid4

import pytest

from app.models.listing import Listing
from app.schemas.listing import listing_to_response


def test_listing_to_response_for_property_listing():
    listing = Listing(
        id=uuid4(),
        property_id=uuid4(),
        transaction_type="sale",
        title="Property for Sale",
        description="Entire property",
        status="draft",
    )

    response = listing_to_response(listing)

    assert response.id == listing.id
    assert response.target_type == "property"
    assert response.target_id == listing.property_id
    assert response.transaction_type == "sale"
    assert response.title == "Property for Sale"
    assert response.description == "Entire property"
    assert response.status == "draft"


def test_listing_to_response_for_floor_listing():
    listing = Listing(
        id=uuid4(),
        floor_id=uuid4(),
        transaction_type="rent",
        title="Floor for Rent",
        description="Entire floor",
        status="published",
    )

    response = listing_to_response(listing)

    assert response.id == listing.id
    assert response.target_type == "floor"
    assert response.target_id == listing.floor_id
    assert response.transaction_type == "rent"
    assert response.title == "Floor for Rent"
    assert response.description == "Entire floor"
    assert response.status == "published"


def test_listing_to_response_for_space_listing():
    listing = Listing(
        id=uuid4(),
        space_id=uuid4(),
        transaction_type="rent",
        title="Office Space",
        description=None,
        status="unpublished",
    )

    response = listing_to_response(listing)

    assert response.id == listing.id
    assert response.target_type == "space"
    assert response.target_id == listing.space_id
    assert response.transaction_type == "rent"
    assert response.title == "Office Space"
    assert response.description is None
    assert response.status == "unpublished"


def test_listing_to_response_rejects_listing_without_target():
    listing = Listing(
        id=uuid4(),
        transaction_type="rent",
        title="Invalid Listing",
        status="draft",
    )

    with pytest.raises(ValueError, match="Listing has no valid target"):
        listing_to_response(listing)
