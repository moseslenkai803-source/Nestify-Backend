import pytest

from app.services.rate_limit_service import (
    RateLimitDecision,
    RateLimitService,
)


def make_service(*, duration=60, max_keys=10, start=100.0):
    clock = [start]
    service = RateLimitService(
        emergency_fallback_seconds=duration,
        emergency_max_keys=max_keys,
        clock=lambda: clock[0],
    )
    return service, clock


def test_fallback_is_unavailable_until_activated():
    service, _ = make_service()

    decision = service.check_emergency_fallback(
        key="ip:192.0.2.1",
        limit=2,
        window_seconds=60,
    )

    assert decision is RateLimitDecision.UNAVAILABLE


def test_fallback_allows_requests_under_limit():
    service, _ = make_service()
    service.activate_emergency_fallback()

    for _ in range(2):
        decision = service.check_emergency_fallback(
            key="ip:192.0.2.1",
            limit=2,
            window_seconds=60,
        )
        assert decision is RateLimitDecision.ALLOWED


def test_fallback_rejects_requests_over_limit():
    service, _ = make_service()
    service.activate_emergency_fallback()

    for _ in range(2):
        service.check_emergency_fallback(
            key="ip:192.0.2.1",
            limit=2,
            window_seconds=60,
        )

    decision = service.check_emergency_fallback(
        key="ip:192.0.2.1",
        limit=2,
        window_seconds=60,
    )

    assert decision is RateLimitDecision.LIMITED


def test_fallback_becomes_unavailable_at_deadline():
    service, clock = make_service(duration=60)
    service.activate_emergency_fallback()

    clock[0] = 159.999
    before_deadline = service.check_emergency_fallback(
        key="ip:192.0.2.1",
        limit=5,
        window_seconds=60,
    )

    clock[0] = 160.0
    at_deadline = service.check_emergency_fallback(
        key="ip:192.0.2.1",
        limit=5,
        window_seconds=60,
    )

    assert before_deadline is RateLimitDecision.ALLOWED
    assert at_deadline is RateLimitDecision.UNAVAILABLE


def test_reactivation_does_not_extend_deadline():
    service, clock = make_service(duration=60)
    service.activate_emergency_fallback()

    clock[0] = 130.0
    service.activate_emergency_fallback()

    clock[0] = 160.0
    decision = service.check_emergency_fallback(
        key="ip:192.0.2.1",
        limit=5,
        window_seconds=60,
    )

    assert decision is RateLimitDecision.UNAVAILABLE


def test_fallback_refuses_new_keys_when_capacity_is_full():
    service, _ = make_service(max_keys=1)
    service.activate_emergency_fallback()

    first = service.check_emergency_fallback(
        key="ip:192.0.2.1",
        limit=5,
        window_seconds=60,
    )
    second = service.check_emergency_fallback(
        key="ip:192.0.2.2",
        limit=5,
        window_seconds=60,
    )

    assert first is RateLimitDecision.ALLOWED
    assert second is RateLimitDecision.UNAVAILABLE


def test_recovery_clears_fallback_state():
    service, _ = make_service()
    service.activate_emergency_fallback()

    service.check_emergency_fallback(
        key="ip:192.0.2.1",
        limit=1,
        window_seconds=60,
    )
    service.recover_store()

    decision = service.check_emergency_fallback(
        key="ip:192.0.2.1",
        limit=1,
        window_seconds=60,
    )

    assert decision is RateLimitDecision.UNAVAILABLE


def test_fallback_allows_request_after_old_request_expires():
    service, clock = make_service()
    service.activate_emergency_fallback()

    first = service.check_emergency_fallback(
        key="ip:192.0.2.1",
        limit=1,
        window_seconds=10,
    )
    clock[0] = 111.0
    second = service.check_emergency_fallback(
        key="ip:192.0.2.1",
        limit=1,
        window_seconds=10,
    )

    assert first is RateLimitDecision.ALLOWED
    assert second is RateLimitDecision.ALLOWED


def test_fallback_reclaims_capacity_from_expired_keys():
    service, clock = make_service(max_keys=1)
    service.activate_emergency_fallback()

    service.check_emergency_fallback(
        key="ip:192.0.2.1",
        limit=1,
        window_seconds=10,
    )

    clock[0] = 111.0
    decision = service.check_emergency_fallback(
        key="ip:192.0.2.2",
        limit=1,
        window_seconds=10,
    )

    assert decision is RateLimitDecision.ALLOWED


@pytest.mark.parametrize(
    ("duration", "max_keys"),
    [
        (0, 10),
        (-1, 10),
        (60, 0),
        (60, -1),
    ],
)
def test_invalid_service_configuration_is_rejected(duration, max_keys):
    with pytest.raises(ValueError):
        RateLimitService(
            emergency_fallback_seconds=duration,
            emergency_max_keys=max_keys,
        )


@pytest.mark.parametrize(
    ("key", "limit", "window_seconds"),
    [
        ("", 1, 60),
        ("ip:192.0.2.1", 0, 60),
        ("ip:192.0.2.1", -1, 60),
        ("ip:192.0.2.1", 1, 0),
        ("ip:192.0.2.1", 1, -1),
        ("ip:192.0.2.1", 1, float("nan")),
        ("ip:192.0.2.1", 1, float("inf")),
        ("ip:192.0.2.1", 1, float("-inf")),
    ],
)
def test_invalid_request_parameters_are_rejected(
    key,
    limit,
    window_seconds,
):
    service, _ = make_service()
    service.activate_emergency_fallback()

    with pytest.raises(ValueError):
        service.check_emergency_fallback(
            key=key,
            limit=limit,
            window_seconds=window_seconds,
        )
