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

    def eval(self, script, numkeys, *args):
        self.calls.append((script, numkeys, args))
        if self.error:
            raise self.error
        self.count += 1
        return self.count


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


def test_redis_success_clears_emergency_fallback():
    client = FakeRedis()
    client.error = RedisConnectionError("connection failed")
    service = make_service(client)

    service.check(
        key="client-1",
        limit=5,
        window_seconds=60,
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
        key="client-1",
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
