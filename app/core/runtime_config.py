import re
from ipaddress import IPv4Address, IPv6Address, ip_address
from urllib.parse import urlsplit

from cryptography.fernet import Fernet

from app.core.config import settings

class RuntimeConfigurationError(RuntimeError):
    """Raised when runtime configuration is unsafe for deployment."""


_VALID_ENVIRONMENTS = {"development", "test", "staging", "production"}
_PROTECTED_ENVIRONMENTS = {"staging", "production"}
_PLACEHOLDER_MARKERS = (
    "replace_with",
    "change_me",
    "changeme",
    "placeholder",
    "your_secret",
    "your-secret",
    "example",
)



def _validate_protected_frontend_base_url() -> None:
    """Require a safe HTTPS frontend URL in staging and production."""
    url = settings.frontend_base_url

    if (
        not isinstance(url, str)
        or not url
        or url != url.strip()
        or any(character.isspace() for character in url)
    ):
        raise RuntimeConfigurationError(
            "FRONTEND_BASE_URL must be a valid HTTPS URL"
        )

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed.port  # Validate malformed and out-of-range ports.

        if not hostname:
            raise ValueError("Missing hostname")

        try:
            ip = ip_address(hostname)
        except ValueError:
            ip = None
            normalized_hostname = hostname.rstrip(".")

            # Reject numeric-looking hosts that failed IP address parsing.
            # Otherwise values such as "1234" or "999.999.999.999"
            # can pass the DNS-label checks despite not being valid IPs.
            if (
                re.fullmatch(r"[0-9.]+", hostname)
                or len(hostname) > 253
                or hostname.endswith("..")
                or not normalized_hostname
                or not all(
                    re.fullmatch(
                        r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",
                        label,
                    )
                    for label in normalized_hostname.split(".")
                )
            ):
                raise ValueError("Invalid hostname")

    except (ValueError, UnicodeError) as exc:
        raise RuntimeConfigurationError(
            "FRONTEND_BASE_URL must be a valid HTTPS URL"
        ) from exc

    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "?" in url
        or "#" in url
        or "*" in hostname
        or hostname.lower() == "localhost"
        or hostname.lower().endswith(".localhost")
        or (ip is not None and (ip.is_loopback or ip.is_unspecified))
    ):
        raise RuntimeConfigurationError(
            "FRONTEND_BASE_URL must use HTTPS and a trusted, non-local host "
            "without credentials, query strings, or fragments"
        )


def _validate_redis_hostname(
    hostname: str,
) -> IPv4Address | IPv6Address | None:
    """Validate a Redis DNS hostname or IP literal."""
    normalized_hostname = hostname.lower().rstrip(".")

    try:
        return ip_address(normalized_hostname)
    except ValueError:
        if (
            re.fullmatch(r"[0-9.]+", hostname)
            or len(hostname) > 253
            or hostname.endswith("..")
            or not normalized_hostname
            or not all(
                re.fullmatch(
                    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",
                    label,
                )
                for label in normalized_hostname.split(".")
            )
        ):
            raise ValueError("Invalid Redis hostname")

        return None


def _validate_redis_configuration() -> None:
    """Require a valid shared Redis URL in staging and production."""
    url = settings.redis_url

    if url is None or url == "":
        raise RuntimeConfigurationError(
            "REDIS_URL must be configured in staging and production"
        )

    if (
        not isinstance(url, str)
        or url != url.strip()
        or any(character.isspace() for character in url)
    ):
        raise RuntimeConfigurationError(
            "REDIS_URL must be a valid redis:// or rediss:// URL"
        )

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed.port  # Validate malformed and out-of-range ports.

        if (
            parsed.scheme not in {"redis", "rediss"}
            or not hostname
            or "?" in url
            or "#" in url
            or (parsed.path and not re.fullmatch(r"/[0-9]+", parsed.path))
        ):
            raise ValueError("Invalid Redis URL")

        ip = _validate_redis_hostname(hostname)

        # Protected environments must use a shared, non-local Redis host.
        normalized_hostname = hostname.lower().rstrip(".")
        is_local_host = (
            normalized_hostname == "localhost"
            or normalized_hostname.endswith(".localhost")
            or (ip is not None and (ip.is_loopback or ip.is_unspecified))
        )

        if (
            is_local_host
            and settings.environment.strip().lower()
            in {"staging", "production"}
        ):
            raise ValueError("Redis must use a shared, non-local host")

    except (ValueError, UnicodeError) as exc:
        raise RuntimeConfigurationError(
            "REDIS_URL must be a valid redis:// or rediss:// URL"
        ) from exc


def _validate_environment() -> str:
    """Validate and return the normalized runtime environment."""
    environment = settings.environment.strip().lower()

    if environment not in _VALID_ENVIRONMENTS:
        raise RuntimeConfigurationError(
            "ENVIRONMENT must be development, test, staging, or production"
        )

    return environment


def _validate_outbox_encryption_configuration() -> None:
    """Require a valid active outbox key and valid configured key ring."""
    keys = settings.outbox_encryption_keys
    active_version = settings.outbox_active_encryption_key_version

    if not keys or not active_version or active_version not in keys:
        raise RuntimeConfigurationError(
            "A valid active outbox encryption key must be configured"
        )

    for version, key in keys.items():
        try:
            if not version or not isinstance(key, str):
                raise ValueError
            Fernet(key.encode("ascii"))
        except (ValueError, TypeError, UnicodeEncodeError) as exc:
            raise RuntimeConfigurationError(
                "All configured outbox encryption keys must be valid Fernet keys"
            ) from exc


def validate_email_worker_configuration() -> None:
    """Validate only the runtime settings required by the email worker."""
    environment = _validate_environment()

    if environment in _PROTECTED_ENVIRONMENTS and settings.debug:
        raise RuntimeConfigurationError(
            "DEBUG must be false in staging and production"
        )

    if environment in _PROTECTED_ENVIRONMENTS:
        _validate_outbox_encryption_configuration()


def validate_runtime_configuration() -> None:
    """Reject unknown environments and unsafe staging/production settings."""
    environment = _validate_environment()

    if environment not in _PROTECTED_ENVIRONMENTS:
        return

    if settings.debug:
        raise RuntimeConfigurationError(
            "DEBUG must be false in staging and production"
        )

    _validate_protected_frontend_base_url()
    _validate_redis_configuration()

    jwt_secret = settings.jwt_secret_key.strip()
    if (
        len(jwt_secret) < 32
        or any(marker in jwt_secret.lower() for marker in _PLACEHOLDER_MARKERS)
    ):
        raise RuntimeConfigurationError(
            "JWT_SECRET_KEY must be a non-placeholder secret of at least 32 characters"
        )

    _validate_outbox_encryption_configuration()

    origins = settings.cors_allowed_origins
    if not origins:
        raise RuntimeConfigurationError(
            "CORS_ALLOWED_ORIGINS must contain trusted HTTPS origins in staging and production"
        )

    for origin in origins:
        if (
            not isinstance(origin, str)
            or not origin
            or origin != origin.strip()
        ):
            raise RuntimeConfigurationError(
                "CORS_ALLOWED_ORIGINS contains an invalid origin"
            )

        try:
            parsed = urlsplit(origin)
            hostname = parsed.hostname
            parsed.port  # Force validation of malformed or out-of-range ports.
            if not hostname:
                raise ValueError

            # IP literals are valid hosts; other hosts must use valid DNS labels.
            try:
                ip = ip_address(hostname)
            except ValueError:
                ip = None
                if (
                    re.fullmatch(r"[0-9.]+", hostname)
                    or len(hostname) > 253
                    or not all(
                        re.fullmatch(
                            r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",
                            label,
                        )
                        for label in hostname.rstrip(".").split(".")
                    )
                    or hostname.endswith("..")
                ):
                    raise ValueError("Invalid hostname")
        except (ValueError, UnicodeError) as exc:
            raise RuntimeConfigurationError(
                "CORS_ALLOWED_ORIGINS contains an invalid origin"
            ) from exc

        if (
            parsed.scheme != "https"
            or origin != f"{parsed.scheme}://{parsed.netloc}"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or "?" in origin
            or "#" in origin
            or "*" in hostname
            or hostname.lower() == "localhost"
            or (ip is not None and (ip.is_loopback or ip.is_unspecified))
        ):
            raise RuntimeConfigurationError(
                "CORS_ALLOWED_ORIGINS must contain explicit HTTPS origins without paths, wildcards, or localhost"
            )
