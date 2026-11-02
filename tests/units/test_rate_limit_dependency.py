import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.api.rate_limit import (
    get_rate_limit_service,
    rate_limit_dependency,
)
from app.services.rate_limit_service import RateLimitDecision


class FakeRateLimitService:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def check(self, **kwargs):
        self.calls.append(kwargs)
        return self.decision


def make_client(decision):
    service = FakeRateLimitService(decision)
    app = FastAPI()

    app.dependency_overrides[get_rate_limit_service] = lambda: service

    @app.post(
        "/limited",
        dependencies=[
            Depends(
                rate_limit_dependency(
                    policy_name="test-login",
                    limit=5,
                    window_seconds=60,
                )
            )
        ],
    )
    def endpoint():
        return {"status": "processed"}

    return TestClient(app), service


def test_allows_request_when_limiter_allows():
    client, service = make_client(RateLimitDecision.ALLOWED)

    response = client.post("/limited")

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    assert service.calls[0]["policy_name"] == "test-login"
    assert service.calls[0]["limit"] == 5
    assert service.calls[0]["window_seconds"] == 60


def test_returns_429_and_retry_after_when_limited():
    client, _ = make_client(RateLimitDecision.LIMITED)

    response = client.post("/limited")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"


def test_returns_503_when_limiter_is_unavailable():
    client, _ = make_client(RateLimitDecision.UNAVAILABLE)

    response = client.post("/limited")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Request processing is temporarily unavailable."
    )


def test_account_limit_uses_normalized_email():
    service = FakeRateLimitService(RateLimitDecision.ALLOWED)
    app = FastAPI()
    app.dependency_overrides[get_rate_limit_service] = lambda: service

    @app.post(
        "/account-limited",
        dependencies=[
            Depends(
                rate_limit_dependency(
                    policy_name="auth-login-account",
                    limit=5,
                    window_seconds=300,
                    identity_field="email",
                )
            )
        ],
    )
    def endpoint():
        return {"status": "processed"}

    with TestClient(app) as client:
        response = client.post(
            "/account-limited",
            json={"email": "  Example.User@Example.com  "},
        )

    assert response.status_code == 200
    assert service.calls[0]["key"] == "Example.User@Example.com".strip().lower()
    assert service.calls[0]["policy_name"] == "auth-login-account"
    assert service.calls[0]["limit"] == 5
    assert service.calls[0]["window_seconds"] == 300


def test_account_limit_skips_missing_email_without_shared_bucket():
    service = FakeRateLimitService(RateLimitDecision.ALLOWED)
    app = FastAPI()
    app.dependency_overrides[get_rate_limit_service] = lambda: service

    @app.post(
        "/account-limited",
        dependencies=[
            Depends(
                rate_limit_dependency(
                    policy_name="auth-login-account",
                    limit=5,
                    window_seconds=300,
                    identity_field="email",
                )
            )
        ],
    )
    def endpoint():
        return {"status": "processed"}

    with TestClient(app) as client:
        response = client.post("/account-limited", json={"password": "example"})

    assert response.status_code == 200
    assert service.calls == []


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_ip_limit_uses_cf_connecting_ip_in_deployed_environments(
    monkeypatch, environment
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", environment)
    client, service = make_client(RateLimitDecision.ALLOWED)

    with client:
        response = client.post(
            "/limited",
            headers={
                "CF-Connecting-IP": "203.0.113.42",
                "X-Forwarded-For": "198.51.100.99",
            },
        )

    assert response.status_code == 200
    assert service.calls[0]["key"] == "203.0.113.42"


@pytest.mark.parametrize(
    ("environment", "client_ip", "expected_ip"),
    [
        (
            "production",
            "2001:0db8:0000:0000:0000:0000:0000:0001",
            "2001:db8::1",
        ),
        ("staging", "2001:db8::1", "2001:db8::1"),
    ],
)
def test_ip_limit_normalizes_ipv6_client_addresses(
    monkeypatch, environment, client_ip, expected_ip
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", environment)
    client, service = make_client(RateLimitDecision.ALLOWED)

    with client:
        response = client.post(
            "/limited",
            headers={"CF-Connecting-IP": client_ip},
        )

    assert response.status_code == 200
    assert service.calls[0]["key"] == expected_ip


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"CF-Connecting-IP": "not-an-ip"},
        {"CF-Connecting-IP": "203.0.113.42, 198.51.100.99"},
        {"CF-Connecting-IP": " 203.0.113.42"},
        {"CF-Connecting-IP": "203.0.113.42 "},
    ],
)
def test_ip_limit_fails_closed_for_invalid_cf_client_ip(
    monkeypatch, headers
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    client, service = make_client(RateLimitDecision.ALLOWED)

    with client:
        response = client.post("/limited", headers=headers)

    assert response.status_code == 503
    assert service.calls == []
