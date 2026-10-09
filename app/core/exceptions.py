class AddressPlateRequestNotFoundError(ValueError):
    """Raised when an address plate request does not exist."""


class PropertyAccessDeniedError(ValueError):
    """Raised when an employee lacks access to a property."""
