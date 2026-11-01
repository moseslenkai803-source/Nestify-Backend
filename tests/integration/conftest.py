import pytest

from app.api.rate_limit import get_rate_limit_service
from app.main import app
from app.services.rate_limit_service import RateLimitDecision


class IntegrationRateLimitService:
    """Deterministic limiter for ordinary integration tests."""

    def check(self, **kwargs):
        return RateLimitDecision.ALLOWED


@pytest.fixture(autouse=True)
def override_rate_limit_service():
    """Keep integration tests independent of a live Redis instance."""
    app.dependency_overrides[get_rate_limit_service] = (
        lambda: IntegrationRateLimitService()
    )
    yield
    app.dependency_overrides.pop(get_rate_limit_service, None)
