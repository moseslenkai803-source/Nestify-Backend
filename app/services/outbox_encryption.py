from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class OutboxEncryptionError(RuntimeError):
    """Raised when an outbox payload cannot be safely encrypted or decrypted."""


class OutboxEncryptionService:
    """Encrypt outbox payloads using a configured, versioned Fernet key ring."""

    def __init__(self) -> None:
        self._keys = settings.outbox_encryption_keys
        self._active_version = settings.outbox_active_encryption_key_version

    def _fernet_for_version(self, version: str) -> Fernet:
        key = self._keys.get(version)
        if not key:
            raise OutboxEncryptionError(
                f"No outbox encryption key configured for version {version!r}"
            )

        try:
            return Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise OutboxEncryptionError(
                f"Invalid outbox encryption key for version {version!r}"
            ) from exc

    def encrypt(self, plaintext: bytes) -> tuple[str, str]:
        if not isinstance(plaintext, bytes):
            raise TypeError("Outbox plaintext must be bytes")

        version = self._active_version
        fernet = self._fernet_for_version(version)
        ciphertext = fernet.encrypt(plaintext).decode("ascii")
        return version, ciphertext

    def decrypt(self, version: str, ciphertext: str) -> bytes:
        fernet = self._fernet_for_version(version)
        try:
            return fernet.decrypt(ciphertext.encode("ascii"))
        except (InvalidToken, UnicodeEncodeError) as exc:
            raise OutboxEncryptionError(
                "Outbox payload could not be authenticated or decrypted"
            ) from exc
