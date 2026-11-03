from unittest.mock import Mock

from redis.exceptions import ConnectionError as RedisConnectionError

from app.services.rate_limit_service import (
    RateLimitDecision,
    RateLimitService,
)


class FakeRedis:
    def __init__(self):
        self.calls = []
        self.count = 0
        self.error = None
        self.ping_result = True
        self.ping_error = None

    def eval(self, script, numkeys, *args):
        self.calls.append((script, numkeys, args))
        if self.error:
            raise self.error
        self.count += 1
        return self.count

    def ping(self):
        if self.ping_error:
            raise self.ping_error
        return self.ping_result


def make_service(client=None, **kwargs):
    return RateLimitService(
        redis_client=client or FakeRedis(),
        **kwargs,
    )


def test_shared_store_allows_requests_within_limit():
    client = FakeRedis()
    service = make_service(client)

    first = service.check_shared_store(
        key="192.0.2.10",
        limit=2,
        window_seconds=60,
        policy_name="login",
    )
    second = service.check_shared_store(
        key="192.0.2.10",
        limit=2,
        window_seconds=60,
        policy_name="login",
    )

    assert first is RateLimitDecision.ALLOWED
    assert second is RateLimitDecision.ALLOWED
    assert len(client.calls) == 2


def test_shared_store_limits_requests_over_limit():
    client = FakeRedis()
    client.count = 2
    service = make_service(client)

    result = service.check_shared_store(
        key="account-123",
        limit=2,
        window_seconds=60,
        policy_name="login",
    )

    assert result is RateLimitDecision.LIMITED


def test_redis_key_does_not_contain_raw_identifier():
    client = FakeRedis()
    service = make_service(client)

    service.check_shared_store(
        key="sensitive-account-identifier",
        limit=5,
        window_seconds=60,
        policy_name="login",
    )

    redis_key = client.calls[0][2][0]
    assert "sensitive-account-identifier" not in redis_key
    assert redis_key.startswith("nestify:rate-limit:login:60000:")


def test_redis_failure_returns_unavailable():
    client = FakeRedis()
    client.error = RedisConnectionError("connection failed")
    service = make_service(client)

    result = service.check_shared_store(
        key="client-1",
        limit=5,
        window_seconds=60,
    )

    assert result is RateLimitDecision.UNAVAILABLE


def test_sensitive_check_fails_closed_when_redis_is_unavailable():
    client = FakeRedis()
    client.error = RedisConnectionError("connection failed")
    service = make_service(client)

    result = service.check(
        key="account-123",
        limit=5,
        window_seconds=60,
        policy_name="login",
        allow_emergency_fallback=False,
    )

    assert result is RateLimitDecision.UNAVAILABLE
    assert service.check_emergency_fallback(
        key="login:account-123",
        limit=5,
        window_seconds=60,
    ) is RateLimitDecision.UNAVAILABLE


def test_permitted_check_uses_fallback_when_redis_is_unavailable():
    client = FakeRedis()
    client.error = RedisConnectionError("connection failed")
    service = make_service(client)

    result = service.check(
        key="client-1",
        limit=5,
        window_seconds=60,
        policy_name="public-lookup",
        allow_emergency_fallback=True,
    )

    assert result is RateLimitDecision.ALLOWED


def test_redis_success_starts_emergency_fallback_recovery_grace():
    clock = [100.0]
    client = FakeRedis()
    client.error = RedisConnectionError("connection failed")
    service = make_service(client, clock=lambda: clock[0])

    service.check(
        key="client-1",
        limit=5,
        window_seconds=60,
        policy_name="public-lookup",
        allow_emergency_fallback=True,
    )

    client.error = None
    result = service.check_shared_store(
        key="client-1",
        limit=5,
        window_seconds=60,
    )

    assert result is RateLimitDecision.ALLOWED
    assert service.check_emergency_fallback(
        key="public-lookup:client-1",
        limit=5,
        window_seconds=60,
    ) is RateLimitDecision.ALLOWED

    clock[0] += 5
    service.check_shared_store(
        key="client-1",
        limit=5,
        window_seconds=60,
    )
    assert service.check_emergency_fallback(
        key="public-lookup:client-1",
        limit=5,
        window_seconds=60,
    ) is RateLimitDecision.UNAVAILABLE


def test_store_health_returns_true_when_redis_ping_succeeds():
    client = Mock()
    client.ping.return_value = True
    service = make_service(client)

    assert service.check_store_health() is True
    client.ping.assert_called_once_with()


def test_store_health_returns_false_when_redis_connection_fails():
    client = Mock()
    client.ping.side_effect = RedisConnectionError("connection failed")
    service = make_service(client)

    assert service.check_store_health() is False
    client.ping.assert_called_once_with()


def _assert_ping_failure_restarts_recovery_grace(*, failure_mode):
    clock = [100.0]
    client = FakeRedis()
    client.error = RedisConnectionError("connection failed")
    service = make_service(client, clock=lambda: clock[0])

    service.check(
        key="client-1",
        limit=5,
        window_seconds=60,
        policy_name="public-lookup",
        allow_emergency_fallback=True,
    )

    client.error = None
    service.check_shared_store(
        key="client-1",
        limit=5,
        window_seconds=60,
        policy_name="public-lookup",
    )
    clock[0] += 4

    if failure_mode == "false":
        client.ping_result = False
    else:
        client.ping_error = RedisConnectionError("connection failed")

    assert service.check_store_health() is False

    client.ping_result = True
    client.ping_error = None
    assert service.check_store_health() is True

    clock[0] += 4
    service.check_shared_store(
        key="client-1",
        limit=5,
        window_seconds=60,
        policy_name="public-lookup",
    )
    assert service.check_emergency_fallback(
        key="public-lookup:client-1",
        limit=5,
        window_seconds=60,
    ) is RateLimitDecision.ALLOWED

    clock[0] += 1
    assert service.check_store_health() is True
    assert service.check_emergency_fallback(
        key="public-lookup:client-1",
        limit=5,
        window_seconds=60,
    ) is RateLimitDecision.UNAVAILABLE


def test_false_redis_ping_restarts_recovery_grace_interval():
    _assert_ping_failure_restarts_recovery_grace(failure_mode="false")


def test_redis_ping_exception_restarts_recovery_grace_interval():
    _assert_ping_failure_restarts_recovery_grace(failure_mode="exception")


def test_brief_redis_recovery_does_not_reset_fallback_counters():
    clock = [100.0]
    client = FakeRedis()
    client.error = RedisConnectionError("connection failed")
    service = make_service(client, clock=lambda: clock[0])

    first = service.check(
        key="client-1",
        limit=1,
        window_seconds=60,
        policy_name="public-lookup",
        allow_emergency_fallback=True,
    )

    client.error = None
    recovered = service.check_shared_store(
        key="recovery-probe",
        limit=10,
        window_seconds=60,
        policy_name="recovery-probe",
    )

    client.error = RedisConnectionError("connection failed")
    second = service.check(
        key="client-1",
        limit=1,
        window_seconds=60,
        policy_name="public-lookup",
        allow_emergency_fallback=True,
    )

    assert first is RateLimitDecision.ALLOWED
    assert recovered is RateLimitDecision.ALLOWED
    assert second is RateLimitDecision.LIMITED


def test_redis_failure_restarts_recovery_grace_interval():
    clock = [100.0]
    client = FakeRedis()
    client.error = RedisConnectionError("connection failed")
    service = make_service(client, clock=lambda: clock[0])

    service.check(
        key="client-1",
        limit=5,
        window_seconds=60,
        policy_name="public-lookup",
        allow_emergency_fallback=True,
    )

    client.error = None
    service.check_shared_store(
        key="recovery-probe",
        limit=10,
        window_seconds=60,
    )

    clock[0] += 4
    client.error = RedisConnectionError("connection failed")
    service.check(
        key="client-1",
        limit=5,
        window_seconds=60,
        policy_name="public-lookup",
        allow_emergency_fallback=True,
    )

    client.error = None
    service.check_shared_store(
        key="recovery-probe",
        limit=10,
        window_seconds=60,
    )

    clock[0] += 4
    service.check_shared_store(
        key="recovery-probe",
        limit=10,
        window_seconds=60,
    )
    assert service.check_emergency_fallback(
        key="public-lookup:client-1",
        limit=5,
        window_seconds=60,
    ) is RateLimitDecision.ALLOWED

    clock[0] += 1
    service.check_shared_store(
        key="recovery-probe",
        limit=10,
        window_seconds=60,
    )
    assert service.check_emergency_fallback(
        key="public-lookup:client-1",
        limit=5,
        window_seconds=60,
    ) is RateLimitDecision.UNAVAILABLE


def test_redis_limited_response_counts_toward_recovery_grace():
    clock = [100.0]
    client = FakeRedis()
    client.error = RedisConnectionError("connection failed")
    service = make_service(
        client,
        clock=lambda: clock[0],
        recovery_grace_seconds=5.0,
    )

    service.check(
        key="client-1",
        limit=5,
        window_seconds=60,
        policy_name="public-lookup",
        allow_emergency_fallback=True,
    )

    client.error = None
    client.count = 1
    first = service.check_shared_store(
        key="limited-probe",
        limit=1,
        window_seconds=60,
    )
    assert first is RateLimitDecision.LIMITED

    clock[0] += 5
    second = service.check_shared_store(
        key="limited-probe",
        limit=1,
        window_seconds=60,
    )
    assert second is RateLimitDecision.LIMITED

    assert service.check_emergency_fallback(
        key="public-lookup:client-1",
        limit=5,
        window_seconds=60,
    ) is RateLimitDecision.UNAVAILABLE


def test_new_outage_can_activate_fallback_after_sustained_recovery():
    clock = [100.0]
    client = FakeRedis()
    client.error = RedisConnectionError("first outage")
    service = make_service(
        client,
        clock=lambda: clock[0],
        recovery_grace_seconds=5.0,
    )

    first = service.check(
        key="client-1",
        limit=1,
        window_seconds=60,
        policy_name="public-lookup",
        allow_emergency_fallback=True,
    )
    assert first is RateLimitDecision.ALLOWED

    client.error = None
    service.check_shared_store(
        key="recovery-probe",
        limit=10,
        window_seconds=60,
    )
    clock[0] += 5
    service.check_shared_store(
        key="recovery-probe",
        limit=10,
        window_seconds=60,
    )

    client.error = RedisConnectionError("second outage")
    second = service.check(
        key="client-1",
        limit=1,
        window_seconds=60,
        policy_name="public-lookup",
        allow_emergency_fallback=True,
    )

    assert second is RateLimitDecision.ALLOWED
    assert service.check_emergency_fallback(
        key="public-lookup:client-1",
        limit=1,
        window_seconds=60,
    ) is RateLimitDecision.LIMITED
