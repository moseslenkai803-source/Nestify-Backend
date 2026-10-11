SUPPORTED_EMPLOYEE_CLEARANCES = frozenset({
    "plate_operations",
    "installation_verification",
    "property_verification",
    "contractor_management",
})


def validate_employee_clearance(clearance: str) -> str:
    value = clearance.strip()
    if not value:
        raise ValueError("Clearance is required")
    if value not in SUPPORTED_EMPLOYEE_CLEARANCES:
        raise ValueError("Unsupported employee clearance: " + value)
    return value
