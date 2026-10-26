import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.runtime_config import (
    RuntimeConfigurationError,
    validate_runtime_configuration,
)


@pytest.fixture
def safe_production_settings(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(
        settings, "frontend_base_url", "https://app.nestify.example"
    )
    monkeypatch.setattr(
        settings,
        "jwt_secret_key",
        "a-realistic-test-secret-value-that-is-long-enough",
    )
    monkeypatch.setattr(
        settings,
        "outbox_encryption_keys",
        {"v1": Fernet.generate_key().decode("ascii")},
    )
    monkeypatch.setattr(settings, "outbox_active_encryption_key_version", "v1")
    monkeypatch.setattr(
        settings,
        "cors_allowed_origins",
        ["https://app.nestify.example"],
    )


def test_valid_production_configuration_passes(safe_production_settings):
    validate_runtime_configuration()


@pytest.mark.parametrize("environment", ["development", "test"])
def test_non_production_environment_skips_production_only_checks(
    monkeypatch, environment
):
    monkeypatch.setattr(settings, "environment", environment)
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "jwt_secret_key", "short")
    monkeypatch.setattr(settings, "outbox_encryption_keys", {})
    validate_runtime_configuration()



@pytest.mark.parametrize("environment", ["prod", "production-ish", "", "unknown"])
def test_unknown_environment_is_rejected(monkeypatch, environment):
    monkeypatch.setattr(settings, "environment", environment)

    with pytest.raises(RuntimeConfigurationError, match="ENVIRONMENT must be"):
        validate_runtime_configuration()


def test_environment_name_is_normalized(monkeypatch):
    monkeypatch.setattr(settings, "environment", "  DEVELOPMENT  ")
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "jwt_secret_key", "short")
    monkeypatch.setattr(settings, "outbox_encryption_keys", {})

    validate_runtime_configuration()

def test_production_rejects_debug_mode(safe_production_settings, monkeypatch):
    monkeypatch.setattr(settings, "debug", True)

    with pytest.raises(RuntimeConfigurationError, match="DEBUG must be false"):
        validate_runtime_configuration()


@pytest.mark.parametrize(
    "secret",
    [
        "short",
        "replace_with_a_long_random_secret_value",
        "x" * 31,
    ],
)
def test_production_rejects_weak_or_placeholder_jwt_secrets(
    safe_production_settings, monkeypatch, secret
):
    monkeypatch.setattr(settings, "jwt_secret_key", secret)

    with pytest.raises(RuntimeConfigurationError, match="JWT_SECRET_KEY"):
        validate_runtime_configuration()


def test_production_requires_active_outbox_key(
    safe_production_settings, monkeypatch
):
    monkeypatch.setattr(settings, "outbox_encryption_keys", {})
    monkeypatch.setattr(settings, "outbox_active_encryption_key_version", "v1")

    with pytest.raises(RuntimeConfigurationError, match="active outbox"):
        validate_runtime_configuration()


def test_production_rejects_invalid_outbox_key(
    safe_production_settings, monkeypatch
):
    monkeypatch.setattr(settings, "outbox_encryption_keys", {"v1": "invalid-key"})

    with pytest.raises(RuntimeConfigurationError, match="valid Fernet keys"):
        validate_runtime_configuration()


def test_production_requires_active_version_to_exist(
    safe_production_settings, monkeypatch
):
    monkeypatch.setattr(settings, "outbox_active_encryption_key_version", "v2")

    with pytest.raises(RuntimeConfigurationError, match="active outbox"):
        validate_runtime_configuration()


@pytest.mark.parametrize(
    "origins",
    [
        [],
        ["*"],
        ["http://app.nestify.example"],
        ["http://localhost:5173"],
        ["https://localhost"],
        ["https://127.0.0.1"],
        ["https://app.nestify.example/path"],
        ["https://app.nestify.example?next=home"],
        ["https://app.nestify.example?"],
        ["https://app.nestify.example#"],
        ["https://1234"],
        ["https://999.999.999.999"],
        ["not-a-url"],
        [" https://app.nestify.example"],
        ["https://app.nestify.example "],
        ["https://bad host.example"],
        ["https://bad..example"],
        ["https://-bad.example"],
        ["https://bad-.example"],
        ["https://app.nestify.example:invalid"],
        ["https://app.nestify.example:99999"],
        ["https://user:password@app.nestify.example"],
    ],
)
def test_protected_environment_rejects_unsafe_cors_origins(
    safe_production_settings, monkeypatch, origins
):
    monkeypatch.setattr(settings, "cors_allowed_origins", origins)

    with pytest.raises(RuntimeConfigurationError, match="CORS_ALLOWED_ORIGINS"):
        validate_runtime_configuration()


def test_protected_environment_accepts_explicit_https_origins(
    safe_production_settings, monkeypatch
):
    monkeypatch.setattr(
        settings,
        "cors_allowed_origins",
        ["https://app.nestify.example", "https://admin.nestify.example:8443"],
    )

    validate_runtime_configuration()


@pytest.mark.parametrize(
    "frontend_url",
    [
        "",
        "http://app.nestify.example",
        "localhost:5173",
        "https://localhost",
        "https://preview.localhost",
        "https://127.0.0.1",
        "https://0.0.0.0",
        "https://user:password@app.nestify.example",
        "https://app.nestify.example?token=unexpected",
        "https://app.nestify.example?",
        "https://app.nestify.example#fragment",
        "https://app.nestify.example#",
        "https://1234",
        "https://999.999.999.999",
        "https://bad host.example",
        "https://bad..example",
        "https://-bad.example",
        "https://bad-.example",
        "https://app.nestify.example:invalid",
        "https://app.nestify.example:99999",
        " https://app.nestify.example",
        "https://app.nestify.example ",
        "https://*.nestify.example",
    ],
)
def test_protected_environment_rejects_unsafe_frontend_base_urls(
    safe_production_settings, monkeypatch, frontend_url
):
    monkeypatch.setattr(settings, "frontend_base_url", frontend_url)

    with pytest.raises(RuntimeConfigurationError, match="FRONTEND_BASE_URL"):
        validate_runtime_configuration()


@pytest.mark.parametrize(
    "frontend_url",
    [
        "https://app.nestify.example",
        "https://app.nestify.example/",
        "https://app.nestify.example/portal",
        "https://app.nestify.example:8443/portal",
    ],
)
def test_protected_environment_accepts_valid_frontend_base_urls(
    safe_production_settings, monkeypatch, frontend_url
):
    monkeypatch.setattr(settings, "frontend_base_url", frontend_url)

    validate_runtime_configuration()
