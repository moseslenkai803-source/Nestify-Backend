import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import redis

from app.services.rate_limit_service import (
    RateLimitDecision,
    RateLimitService,
)


@pytest.fixture
def redis_url():
    url = os.getenv("NESTIFY_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set NESTIFY_TEST_REDIS_URL to run real Redis integration tests")
    return url


@pytest.fixture
def redis_client(redis_url):
    client = redis.Redis.from_url(
        redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=False,
    )
    client.ping()
    yield client
    client.close()


@pytest.fixture
def service(redis_client):
    return RateLimitService(
        redis_client=redis_client,
        redis_timeout_seconds=1,
    )


def unique_key():
    return f"integration-{uuid.uuid4().hex}"


def test_real_redis_enforces_limit(service):
    key = unique_key()

    results = [
        service.check_shared_store(
            key=key,
            limit=2,
            window_seconds=30,
            policy_name="integration",
        )
        for _ in range(3)
    ]

    assert results == [
        RateLimitDecision.ALLOWED,
        RateLimitDecision.ALLOWED,
        RateLimitDecision.LIMITED,
    ]


def test_real_redis_counter_expires_after_window(service):
    key = unique_key()

    first = service.check_shared_store(
        key=key,
        limit=1,
        window_seconds=0.25,
        policy_name="integration-ttl",
    )
    second = service.check_shared_store(
        key=key,
        limit=1,
        window_seconds=0.25,
        policy_name="integration-ttl",
    )

    assert first is RateLimitDecision.ALLOWED
    assert second is RateLimitDecision.LIMITED

    time.sleep(0.40)

    after_expiry = service.check_shared_store(
        key=key,
        limit=1,
        window_seconds=0.25,
        policy_name="integration-ttl",
    )

    assert after_expiry is RateLimitDecision.ALLOWED


def test_separate_service_instances_share_counter(redis_url):
    key = unique_key()

    client_a = redis.Redis.from_url(
        redis_url, socket_connect_timeout=1, socket_timeout=1
    )
    client_b = redis.Redis.from_url(
        redis_url, socket_connect_timeout=1, socket_timeout=1
    )

    service_a = RateLimitService(redis_client=client_a)
    service_b = RateLimitService(redis_client=client_b)

    try:
        first = service_a.check_shared_store(
            key=key,
            limit=1,
            window_seconds=30,
            policy_name="integration-shared",
        )
        second = service_b.check_shared_store(
            key=key,
            limit=1,
            window_seconds=30,
            policy_name="integration-shared",
        )

        assert first is RateLimitDecision.ALLOWED
        assert second is RateLimitDecision.LIMITED
    finally:
        client_a.close()
        client_b.close()


def test_concurrent_requests_cannot_exceed_limit(service):
    key = unique_key()
    limit = 10
    total_requests = 50

    def make_request(_):
        return service.check_shared_store(
            key=key,
            limit=limit,
            window_seconds=30,
            policy_name="integration-concurrent",
        )

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(make_request, range(total_requests)))

    assert results.count(RateLimitDecision.ALLOWED) == limit
    assert results.count(RateLimitDecision.LIMITED) == total_requests - limit


def test_distinct_policies_have_independent_counters(service):
    key = unique_key()

    first_policy = service.check_shared_store(
        key=key,
        limit=1,
        window_seconds=30,
        policy_name="integration-policy-a",
    )
    second_policy = service.check_shared_store(
        key=key,
        limit=1,
        window_seconds=30,
        policy_name="integration-policy-b",
    )
    repeated_first_policy = service.check_shared_store(
        key=key,
        limit=1,
        window_seconds=30,
        policy_name="integration-policy-a",
    )

    assert first_policy is RateLimitDecision.ALLOWED
    assert second_policy is RateLimitDecision.ALLOWED
    assert repeated_first_policy is RateLimitDecision.LIMITED
