import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.services.outbox_encryption import (
    OutboxEncryptionError,
    OutboxEncryptionService,
)


@pytest.fixture
def encryption_settings(monkeypatch):
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(settings, "outbox_encryption_keys", {"v1": key})
    monkeypatch.setattr(settings, "outbox_active_encryption_key_version", "v1")
    return key


def test_encrypt_decrypt_round_trip(encryption_settings):
    service = OutboxEncryptionService()
    plaintext = b'{"recipient":"employee@example.com","token":"secret-token"}'

    version, ciphertext = service.encrypt(plaintext)

    assert version == "v1"
    assert ciphertext != plaintext.decode("ascii")
    assert "secret-token" not in ciphertext
    assert service.decrypt(version, ciphertext) == plaintext


def test_missing_active_key_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "outbox_encryption_keys", {})
    monkeypatch.setattr(settings, "outbox_active_encryption_key_version", "v1")

    with pytest.raises(OutboxEncryptionError, match="No outbox encryption key"):
        OutboxEncryptionService().encrypt(b"payload")


def test_invalid_key_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "outbox_encryption_keys", {"v1": "not-a-fernet-key"})
    monkeypatch.setattr(settings, "outbox_active_encryption_key_version", "v1")

    with pytest.raises(OutboxEncryptionError, match="Invalid outbox encryption key"):
        OutboxEncryptionService().encrypt(b"payload")


def test_unknown_key_version_fails_closed(encryption_settings):
    service = OutboxEncryptionService()

    with pytest.raises(OutboxEncryptionError, match="No outbox encryption key"):
        service.decrypt("v2", "ciphertext")


def test_tampered_ciphertext_is_rejected(encryption_settings):
    service = OutboxEncryptionService()
    version, ciphertext = service.encrypt(b"sensitive payload")
    tampered = ("A" if ciphertext[0] != "A" else "B") + ciphertext[1:]

    with pytest.raises(
        OutboxEncryptionError,
        match="could not be authenticated or decrypted",
    ):
        service.decrypt(version, tampered)


def test_previous_key_can_decrypt_during_rotation(monkeypatch):
    old_key = Fernet.generate_key().decode("ascii")
    new_key = Fernet.generate_key().decode("ascii")
    old_ciphertext = Fernet(old_key.encode("ascii")).encrypt(b"old queued message")

    monkeypatch.setattr(
        settings,
        "outbox_encryption_keys",
        {"v1": old_key, "v2": new_key},
    )
    monkeypatch.setattr(settings, "outbox_active_encryption_key_version", "v2")
    service = OutboxEncryptionService()

    version, new_ciphertext = service.encrypt(b"new message")

    assert version == "v2"
    assert service.decrypt("v1", old_ciphertext.decode("ascii")) == b"old queued message"
    assert service.decrypt(version, new_ciphertext) == b"new message"
