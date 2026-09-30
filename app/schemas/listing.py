from uuid import UUID

from pydantic import BaseModel


class ListingCreate(BaseModel):
    transaction_type: str
    title: str
    description: str | None = None


class ListingResponse(BaseModel):
    id: UUID
    target_type: str
    target_id: UUID
    transaction_type: str
    title: str
    description: str | None
    status: str


def listing_to_response(listing) -> ListingResponse:
    if listing.property_id is not None:
        target_type = "property"
        target_id = listing.property_id
    elif listing.floor_id is not None:
        target_type = "floor"
        target_id = listing.floor_id
    elif listing.space_id is not None:
        target_type = "space"
        target_id = listing.space_id
    else:
        raise ValueError("Listing has no valid target")

    return ListingResponse(
        id=listing.id,
        target_type=target_type,
        target_id=target_id,
        transaction_type=listing.transaction_type,
        title=listing.title,
        description=listing.description,
        status=listing.status,
    )
