import hashlib
import math
import logging
import time
from collections import deque
from enum import Enum
from threading import RLock
from typing import Callable

import redis
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)


class RateLimitDecision(str, Enum):
    ALLOWED = "allowed"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


_INCREMENT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RateLimitService:
    """Shared Redis rate limiter with a bounded local emergency fallback."""

    def __init__(
        self,
        *,
        redis_client=None,
        redis_url: str | None = None,
        redis_timeout_seconds: float = 0.25,
        emergency_fallback_seconds: float = 60,
        emergency_max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if redis_timeout_seconds <= 0 or redis_timeout_seconds > 1:
            raise ValueError(
                "redis_timeout_seconds must be greater than 0 and at most 1"
            )
        if emergency_fallback_seconds <= 0:
            raise ValueError("emergency_fallback_seconds must be positive")
        if emergency_max_keys < 1:
            raise ValueError("emergency_max_keys must be at least 1")

        self._redis_client = redis_client
        self._redis_url = redis_url
        self._redis_timeout_seconds = redis_timeout_seconds
        self._fallback_seconds = emergency_fallback_seconds
        self._max_keys = emergency_max_keys
        self._clock = clock
        self._lock = RLock()
        self._fallback_deadline: float | None = None
        self._requests: dict[str, deque[float]] = {}

    def _get_redis_client(self):
        """Create the client lazily; do not connect during application startup."""
        if self._redis_client is not None:
            return self._redis_client

        redis_url = self._redis_url
        timeout = self._redis_timeout_seconds

        if redis_url is None:
            from app.core.config import settings

            redis_url = settings.redis_url
            timeout = settings.rate_limit_redis_timeout_seconds

        if not redis_url:
            raise RedisError("Redis URL is not configured")

        self._redis_client = redis.Redis.from_url(
            redis_url,
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
            decode_responses=False,
            retry_on_timeout=False,
        )
        return self._redis_client

    def check_store_health(self) -> bool:
        """Return whether Redis responds to a bounded, read-only health check."""
        try:
            return bool(self._get_redis_client().ping())
        except (RedisError, OSError, TimeoutError) as exc:
            logger.warning(
                "Rate-limit shared store health check failed; error_type=%s",
                type(exc).__name__,
            )
            return False

    @staticmethod
    def _redis_key(*, policy_name: str, key: str, window_ms: int) -> str:
        """Avoid exposing raw account identifiers or client addresses in Redis."""
        digest = hashlib.sha256(
            f"{policy_name}\0{key}".encode("utf-8")
        ).hexdigest()
        return f"nestify:rate-limit:{policy_name}:{window_ms}:{digest}"

    def check_shared_store(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: float,
        policy_name: str = "default",
    ) -> RateLimitDecision:
        """Check and increment a shared Redis counter atomically."""
        self._validate_request(key, limit, window_seconds, policy_name)

        window_ms = max(1, int(window_seconds * 1000))
        redis_key = self._redis_key(
            policy_name=policy_name,
            key=key,
            window_ms=window_ms,
        )

        try:
            count = self._get_redis_client().eval(
                _INCREMENT_SCRIPT,
                1,
                redis_key,
                window_ms,
            )
        except (RedisError, OSError, TimeoutError) as exc:
            logger.warning(
                "Rate-limit shared store unavailable; error_type=%s",
                type(exc).__name__,
            )
            return RateLimitDecision.UNAVAILABLE

        if int(count) > limit:
            return RateLimitDecision.LIMITED

        self.recover_store()
        return RateLimitDecision.ALLOWED

    def check(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: float,
        policy_name: str = "default",
        allow_emergency_fallback: bool = True,
    ) -> RateLimitDecision:
        """
        Prefer Redis. Use local fallback only when the caller permits it.

        Sensitive operations should set allow_emergency_fallback=False.
        """
        self._validate_request(key, limit, window_seconds, policy_name)

        decision = self.check_shared_store(
            key=key,
            limit=limit,
            window_seconds=window_seconds,
            policy_name=policy_name,
        )

        if decision is not RateLimitDecision.UNAVAILABLE:
            return decision

        if not allow_emergency_fallback:
            return RateLimitDecision.UNAVAILABLE

        self.activate_emergency_fallback()

        return self.check_emergency_fallback(
            key=f"{policy_name}:{key}",
            limit=limit,
            window_seconds=window_seconds,
        )

    @staticmethod
    def _validate_request(
        key: str,
        limit: int,
        window_seconds: float,
        policy_name: str,
    ) -> None:
        if not key:
            raise ValueError("key must not be empty")
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if not math.isfinite(window_seconds) or window_seconds <= 0:
            raise ValueError("window_seconds must be finite and positive")
        if not policy_name or ":" in policy_name or any(
            character.isspace() for character in policy_name
        ):
            raise ValueError("policy_name must be non-empty and contain no spaces or colons")

    def activate_emergency_fallback(self) -> None:
        """Start fallback mode without extending an active outage."""
        with self._lock:
            if self._fallback_deadline is not None:
                return

            self._fallback_deadline = self._clock() + self._fallback_seconds
            self._requests.clear()
            logger.warning("Rate-limit emergency fallback activated")

    def recover_store(self) -> None:
        """Clear fallback state after a successful shared-store decision."""
        with self._lock:
            was_active = self._fallback_deadline is not None
            self._fallback_deadline = None
            self._requests.clear()

            if was_active:
                logger.info("Rate-limit shared store recovered")

    def check_emergency_fallback(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: float,
    ) -> RateLimitDecision:
        """Check a request against the bounded process-local fallback."""
        if not key:
            raise ValueError("key must not be empty")
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if not math.isfinite(window_seconds) or window_seconds <= 0:
            raise ValueError("window_seconds must be finite and positive")

        with self._lock:
            now = self._clock()
            deadline = self._fallback_deadline

            if deadline is None or now >= deadline:
                return RateLimitDecision.UNAVAILABLE

            cutoff = now - window_seconds
            expired_keys = []

            for existing_key, timestamps in self._requests.items():
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()

                if not timestamps:
                    expired_keys.append(existing_key)

            for expired_key in expired_keys:
                del self._requests[expired_key]

            timestamps = self._requests.get(key)

            if timestamps is None:
                if len(self._requests) >= self._max_keys:
                    logger.error(
                        "Rate-limit emergency fallback capacity exhausted"
                    )
                    return RateLimitDecision.UNAVAILABLE

                timestamps = deque()
                self._requests[key] = timestamps

            if len(timestamps) >= limit:
                return RateLimitDecision.LIMITED

            timestamps.append(now)
            return RateLimitDecision.ALLOWED
