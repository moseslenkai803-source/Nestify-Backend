from app.models.base import Base
from app.models.landlord import Landlord
from app.models.property import Property
from app.models.user import User
from app.models.property_address import PropertyAddress
from app.models.address_plate import AddressPlate

__all__ = [
    "Base",
    "User",
    "Landlord",
    "Property",
    "PropertyAddress",
    "AddressPlate",
]
