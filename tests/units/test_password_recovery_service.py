import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.models.password_reset_otp_challenge import PasswordResetOtpChallenge
from app.services import password_recovery_service as recovery_module
from app.services.password_recovery_service import PasswordRecoveryService


TEST_PEPPER = "test-only-dedicated-otp-pepper-value-123456"


@pytest.fixture
def recovery_dependencies(monkeypatch):
    db = MagicMock()
    db.scalar.return_value = None
    repository = MagicMock()
    outbox = MagicMock()

    monkeypatch.setattr(recovery_module, "UserRepository", lambda session: repository)
    monkeypatch.setattr(
        recovery_module,
        "EmailOutboxEnqueueService",
        lambda session: outbox,
    )
    monkeypatch.setattr(settings, "password_reset_otp_pepper", TEST_PEPPER)

    return SimpleNamespace(
        db=db,
        repository=repository,
        outbox=outbox,
        service=PasswordRecoveryService(db),
    )


def make_user(**overrides):
    values = {
        "id": uuid.uuid4(),
        "email": "person@example.com",
        "is_active": True,
        "password_hash": "old-hash",
        "token_version": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_challenge(user_id, **overrides):
    values = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "otp_hash": "",
        "expires_at": datetime.now(UTC) + timedelta(minutes=10),
        "attempt_count": 0,
        "verified_at": None,
        "reset_grant_hash": None,
        "reset_grant_expires_at": None,
        "consumed_at": None,
        "created_at": datetime.now(UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_request_password_reset_stores_hashed_otp_and_queues_email(
    recovery_dependencies,
    monkeypatch,
):
    deps = recovery_dependencies
    user = make_user()
    deps.repository.get_by_email.return_value = user
    deps.repository.get_by_id_for_update.return_value = user

    monkeypatch.setattr(recovery_module.secrets, "randbelow", lambda limit: 123456)

    assert deps.service.request_password_reset(email=" PERSON@EXAMPLE.COM ")

    deps.repository.get_by_email.assert_called_once_with("person@example.com")
    deps.repository.get_by_id_for_update.assert_called_once_with(user.id)

    challenge = next(
        item
        for call in deps.db.add.call_args_list
        for item in call.args
        if isinstance(item, PasswordResetOtpChallenge)
    )

    assert challenge.user_id == user.id
    assert challenge.otp_hash == deps.service._otp_hash(challenge.id, "123456")
    assert challenge.otp_hash != "123456"
    assert challenge.expires_at > datetime.now(UTC)
    assert challenge.attempt_count == 0

    deps.outbox.enqueue.assert_called_once()
    kwargs = deps.outbox.enqueue.call_args.kwargs
    assert kwargs["event_type"] == "password_reset_otp"
    assert kwargs["payload"]["recipient"] == user.email
    assert kwargs["payload"]["otp"] == "123456"
    assert "expires_at" in kwargs["payload"]
    deps.db.execute.assert_called_once()
    deps.db.flush.assert_called_once()


def test_request_password_reset_does_not_issue_challenge_for_unknown_user(
    recovery_dependencies,
):
    deps = recovery_dependencies
    deps.repository.get_by_email.return_value = None

    assert not deps.service.request_password_reset(email="unknown@example.com")

    deps.repository.get_by_id_for_update.assert_not_called()
    deps.db.add.assert_not_called()
    deps.outbox.enqueue.assert_not_called()


def test_request_password_reset_respects_resend_cooldown(
    recovery_dependencies,
):
    deps = recovery_dependencies
    user = make_user()
    latest = make_challenge(
        user.id,
        created_at=datetime.now(UTC) - timedelta(seconds=20),
    )
    deps.repository.get_by_email.return_value = user
    deps.repository.get_by_id_for_update.return_value = user
    deps.db.scalar.return_value = latest

    assert not deps.service.request_password_reset(email=user.email)

    deps.db.execute.assert_not_called()
    deps.db.add.assert_not_called()
    deps.outbox.enqueue.assert_not_called()


def test_verify_password_reset_otp_persists_failed_attempt(
    recovery_dependencies,
):
    deps = recovery_dependencies
    user = make_user()
    challenge = make_challenge(user.id)
    challenge.otp_hash = deps.service._otp_hash(challenge.id, "123456")

    deps.repository.get_by_email.return_value = user
    deps.repository.get_by_id_for_update.return_value = user
    deps.db.scalar.return_value = challenge

    result = deps.service.verify_password_reset_otp(
        email=user.email,
        otp="654321",
    )

    assert result is None
    assert challenge.attempt_count == 1
    deps.db.flush.assert_called_once()
    deps.outbox.enqueue.assert_not_called()


def test_verify_password_reset_otp_rejects_challenge_at_attempt_limit(
    recovery_dependencies,
):
    deps = recovery_dependencies
    user = make_user()
    challenge = make_challenge(user.id, attempt_count=5)

    deps.repository.get_by_email.return_value = user
    deps.repository.get_by_id_for_update.return_value = user
    deps.db.scalar.return_value = challenge

    result = deps.service.verify_password_reset_otp(
        email=user.email,
        otp="123456",
    )

    assert result is None
    assert challenge.attempt_count == 5
    deps.db.flush.assert_not_called()


def test_verify_password_reset_otp_rejects_expired_challenge(
    recovery_dependencies,
):
    deps = recovery_dependencies
    user = make_user()
    challenge = make_challenge(
        user.id,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    deps.repository.get_by_email.return_value = user
    deps.repository.get_by_id_for_update.return_value = user
    deps.db.scalar.return_value = challenge

    result = deps.service.verify_password_reset_otp(
        email=user.email,
        otp="123456",
    )

    assert result is None
    deps.db.flush.assert_not_called()


def test_verify_password_reset_otp_issues_hashed_short_lived_grant(
    recovery_dependencies,
    monkeypatch,
):
    deps = recovery_dependencies
    user = make_user()
    challenge = make_challenge(user.id)
    challenge.otp_hash = deps.service._otp_hash(challenge.id, "123456")
    raw_grant = "G" * 43

    deps.repository.get_by_email.return_value = user
    deps.repository.get_by_id_for_update.return_value = user
    deps.db.scalar.return_value = challenge
    monkeypatch.setattr(
        recovery_module.secrets,
        "token_urlsafe",
        lambda length: raw_grant,
    )

    result = deps.service.verify_password_reset_otp(
        email=user.email,
        otp="123456",
    )

    assert result == raw_grant
    assert challenge.verified_at is not None
    assert challenge.reset_grant_hash == deps.service._grant_hash(raw_grant)
    assert challenge.reset_grant_hash != raw_grant
    assert challenge.reset_grant_expires_at > datetime.now(UTC)
    assert challenge.reset_grant_expires_at <= (
        datetime.now(UTC) + timedelta(minutes=6)
    )
    deps.db.flush.assert_called_once()


def test_confirm_password_reset_updates_password_consumes_grant_and_revokes_sessions(
    recovery_dependencies,
    monkeypatch,
):
    deps = recovery_dependencies
    user = make_user()
    raw_grant = "R" * 43
    challenge = make_challenge(
        user.id,
        verified_at=datetime.now(UTC),
        reset_grant_hash=deps.service._grant_hash(raw_grant),
        reset_grant_expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    deps.db.scalar.side_effect = [challenge, challenge]
    deps.repository.get_by_id_for_update.return_value = user
    monkeypatch.setattr(recovery_module, "hash_password", lambda password: "new-hash")

    deps.service.confirm_password_reset(
        email=user.email,
        reset_grant=raw_grant,
        new_password="a-secure-password",
    )

    assert user.password_hash == "new-hash"
    assert user.token_version == 1
    assert challenge.consumed_at is not None
    deps.repository.get_by_id_for_update.assert_called_once_with(user.id)
    deps.outbox.enqueue.assert_called_once_with(
        event_type="password_changed",
        payload={"recipient": user.email},
    )
    deps.db.flush.assert_called_once()


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_confirm_password_reset_rejects_password_outside_policy(
    recovery_dependencies,
    password,
):
    deps = recovery_dependencies

    with pytest.raises(ValueError, match="between 12 and 128"):
        deps.service.confirm_password_reset(
            email="person@example.com",
            reset_grant="R" * 43,
            new_password=password,
        )

    deps.db.scalar.assert_not_called()


def test_confirm_password_reset_rejects_unknown_grant(
    recovery_dependencies,
):
    deps = recovery_dependencies
    deps.db.scalar.return_value = None

    with pytest.raises(ValueError, match="invalid or has expired"):
        deps.service.confirm_password_reset(
            email="person@example.com",
            reset_grant="R" * 43,
            new_password="a-secure-password",
        )

    deps.repository.get_by_id_for_update.assert_not_called()
    deps.outbox.enqueue.assert_not_called()


def test_confirm_password_reset_rejects_email_mismatch(
    recovery_dependencies,
):
    deps = recovery_dependencies
    user = make_user(email="person@example.com")
    challenge = make_challenge(user.id)
    deps.db.scalar.return_value = challenge
    deps.repository.get_by_id_for_update.return_value = user

    with pytest.raises(ValueError, match="invalid or has expired"):
        deps.service.confirm_password_reset(
            email="someone-else@example.com",
            reset_grant="R" * 43,
            new_password="a-secure-password",
        )

    assert deps.db.scalar.call_count == 1
    deps.outbox.enqueue.assert_not_called()


def test_confirm_password_reset_rejects_expired_grant(
    recovery_dependencies,
):
    deps = recovery_dependencies
    user = make_user()
    raw_grant = "R" * 43
    challenge = make_challenge(
        user.id,
        verified_at=datetime.now(UTC),
        reset_grant_hash=deps.service._grant_hash(raw_grant),
        reset_grant_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    deps.db.scalar.side_effect = [challenge, challenge]
    deps.repository.get_by_id_for_update.return_value = user

    with pytest.raises(ValueError, match="invalid or has expired"):
        deps.service.confirm_password_reset(
            email=user.email,
            reset_grant=raw_grant,
            new_password="a-secure-password",
        )

    assert user.password_hash == "old-hash"
    assert user.token_version == 0
    deps.outbox.enqueue.assert_not_called()
