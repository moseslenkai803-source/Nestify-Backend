from functools import lru_cache
from ipaddress import ip_address
from math import ceil

from fastapi import Depends, HTTPException, Request

from app.core.config import settings

from app.services.rate_limit_service import (
    RateLimitDecision,
    RateLimitService,
)


@lru_cache(maxsize=1)
def get_rate_limit_service() -> RateLimitService:
    """Return one reusable service; Redis connections remain lazy."""
    return RateLimitService()


def rate_limit_dependency(
    *,
    policy_name: str,
    limit: int,
    window_seconds: int,
    allow_emergency_fallback: bool = False,
    identity_field: str | None = None,
):
    """Build a FastAPI dependency for an explicit rate-limit policy."""

    async def enforce_rate_limit(
        request: Request,
        service: RateLimitService = Depends(get_rate_limit_service),
    ) -> None:
        if identity_field is None:
            environment = settings.environment.strip().lower()

            if environment in {"staging", "production"}:
                client_ip = request.headers.get("CF-Connecting-IP")

                try:
                    if not client_ip or client_ip != client_ip.strip():
                        raise ValueError("Missing or malformed client IP")

                    # Accept one IP address only, never a forwarded chain.
                    key = str(ip_address(client_ip))
                except ValueError:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Request processing is temporarily unavailable."
                        ),
                    ) from None
            else:
                key = (
                    request.client.host
                    if request.client is not None
                    else "unknown"
                )
        else:
            try:
                payload = await request.json()
            except (ValueError, UnicodeDecodeError):
                payload = None

            identifier = (
                payload.get(identity_field)
                if isinstance(payload, dict)
                else None
            )

            # The separate IP policy still protects malformed or missing
            # identity fields. Do not create a shared "missing email" bucket.
            if not isinstance(identifier, str) or not identifier.strip():
                return

            key = identifier.strip().lower()

        decision = service.check(
            key=key,
            limit=limit,
            window_seconds=window_seconds,
            policy_name=policy_name,
            allow_emergency_fallback=allow_emergency_fallback,
        )

        if decision is RateLimitDecision.LIMITED:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
                headers={
                    "Retry-After": str(max(1, ceil(window_seconds))),
                },
            )

        if decision is RateLimitDecision.UNAVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Request processing is temporarily unavailable.",
            )

    return enforce_rate_limit
