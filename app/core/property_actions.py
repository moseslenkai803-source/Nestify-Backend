from enum import Enum


class PropertyAction(str, Enum):
    PROPERTY_MANAGEMENT = "property_management"
    PLATE_OPERATIONS = "plate_operations"
    PROPERTY_VERIFICATION = "property_verification"
