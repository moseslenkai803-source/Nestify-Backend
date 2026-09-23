import uuid
from datetime import datetime

from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.models.property_location import PropertyLocation
from app.repositories.property_location_repository import PropertyLocationRepository
from app.repositories.property_repository import PropertyRepository


class PropertyLocationService:
    def __init__(self, db: Session):
        self.property_repository = PropertyRepository(db)
        self.property_location_repository = PropertyLocationRepository(db)

    def get_location(
        self,
        property_id: uuid.UUID,
    ) -> PropertyLocation:
        location = self.property_location_repository.get_by_property_id(
            property_id
        )

        if location is None:
            raise ValueError("Property location not found")

        return location

    def create_location(
        self,
        property_id: uuid.UUID,
        latitude: float,
        longitude: float,
        source: str,
        capture_method: str,
        captured_at: datetime,
        accuracy_meters: float | None = None,
    ) -> PropertyLocation:
        property = self.property_repository.get_by_id(property_id)

        if property is None:
            raise ValueError("Property not found")

        existing_location = self.property_location_repository.get_by_property_id(
            property_id
        )

        if existing_location is not None:
            raise ValueError("Property already has a location")

        if not -90 <= latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90")

        if not -180 <= longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180")

        if accuracy_meters is not None and accuracy_meters < 0:
            raise ValueError("Accuracy must be greater than or equal to 0")

        location = WKTElement(
            f"POINT({longitude} {latitude})",
            srid=4326,
        )

        property_location = PropertyLocation(
            property_id=property_id,
            latitude=latitude,
            longitude=longitude,
            location=location,
            source=source,
            capture_method=capture_method,
            accuracy_meters=accuracy_meters,
            captured_at=captured_at,
            status="unverified",
        )

        return self.property_location_repository.add(property_location)
