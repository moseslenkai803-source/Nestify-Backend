import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.models.password_reset_token import PasswordResetToken
from app.services import password_recovery_service as recovery_module
from app.services.password_recovery_service import PasswordRecoveryService


@pytest.fixture
def recovery_dependencies(monkeypatch):
    db = MagicMock()
    repository = MagicMock()
    outbox = MagicMock()

    monkeypatch.setattr(
        recovery_module,
        "UserRepository",
        lambda session: repository,
    )
    monkeypatch.setattr(
        recovery_module,
        "EmailOutboxEnqueueService",
        lambda session: outbox,
    )

    service = PasswordRecoveryService(db)

    return SimpleNamespace(
        db=db,
        repository=repository,
        outbox=outbox,
        service=service,
    )


def test_request_password_reset_stores_only_token_hash_and_queues_encrypted_event(
    recovery_dependencies,
    monkeypatch,
):
    deps = recovery_dependencies
    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="person@example.com",
        is_active=True,
    )
    raw_token = "a" * 43

    deps.repository.get_by_email.return_value = user
    deps.repository.get_by_id_for_update.return_value = user

    monkeypatch.setattr(
        recovery_module.secrets,
        "token_urlsafe",
        lambda length: raw_token,
    )
    monkeypatch.setattr(settings, "frontend_base_url", "https://nestify.example")

    result = deps.service.request_password_reset(
        email=" PERSON@EXAMPLE.COM "
    )

    assert result is True
    deps.repository.get_by_email.assert_called_once_with("person@example.com")
    deps.repository.get_by_id_for_update.assert_called_once_with(user.id)

    token = next(
        call.args[0]
        for call in deps.db.add.call_args_list
        if isinstance(call.args[0], PasswordResetToken)
    )

    assert token.user_id == user.id
    assert token.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
    assert token.token_hash != raw_token
    assert token.expires_at > datetime.now(UTC)
    assert token.expires_at <= datetime.now(UTC) + timedelta(minutes=31)

    deps.outbox.enqueue.assert_called_once()
    kwargs = deps.outbox.enqueue.call_args.kwargs
    assert kwargs["event_type"] == "password_reset"
    assert kwargs["payload"]["recipient"] == user.email
    assert raw_token in kwargs["payload"]["reset_url"]
    assert raw_token not in token.token_hash
    assert deps.db.flush.call_count >= 1


def test_request_password_reset_does_not_issue_token_for_unknown_user(
    recovery_dependencies,
):
    deps = recovery_dependencies
    deps.repository.get_by_email.return_value = None

    result = deps.service.request_password_reset(email="unknown@example.com")

    assert result is False
    deps.repository.get_by_id_for_update.assert_not_called()
    deps.db.add.assert_not_called()
    deps.outbox.enqueue.assert_not_called()


def test_request_password_reset_does_not_issue_token_for_inactive_user(
    recovery_dependencies,
):
    deps = recovery_dependencies
    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="inactive@example.com",
        is_active=False,
    )
    deps.repository.get_by_email.return_value = user

    result = deps.service.request_password_reset(email=user.email)

    assert result is False
    deps.repository.get_by_id_for_update.assert_not_called()
    deps.db.add.assert_not_called()
    deps.outbox.enqueue.assert_not_called()


def test_confirm_password_reset_updates_password_consumes_tokens_and_queues_notice(
    recovery_dependencies,
    monkeypatch,
):
    deps = recovery_dependencies
    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="person@example.com",
        is_active=True,
        password_hash="old-hash",
    )
    raw_token = "b" * 43
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )

    deps.db.scalar.side_effect = [user.id, reset_token]
    deps.repository.get_by_id_for_update.return_value = user
    monkeypatch.setattr(
        recovery_module,
        "hash_password",
        lambda password: "new-hash",
    )

    deps.service.confirm_password_reset(
        token=raw_token,
        new_password="a-secure-password",
    )

    assert user.password_hash == "new-hash"
    deps.repository.get_by_id_for_update.assert_called_once_with(user.id)
    deps.db.execute.assert_called_once()
    deps.outbox.enqueue.assert_called_once_with(
        event_type="password_changed",
        payload={"recipient": user.email},
    )
    deps.db.flush.assert_called()


@pytest.mark.parametrize(
    "password",
    ["short", "x" * 129],
)
def test_confirm_password_reset_rejects_password_outside_policy(
    recovery_dependencies,
    password,
):
    deps = recovery_dependencies

    with pytest.raises(ValueError, match="between 12 and 128"):
        deps.service.confirm_password_reset(
            token="c" * 43,
            new_password=password,
        )

    deps.db.scalar.assert_not_called()
    deps.outbox.enqueue.assert_not_called()


def test_confirm_password_reset_rejects_unknown_token(
    recovery_dependencies,
):
    deps = recovery_dependencies
    deps.db.scalar.return_value = None

    with pytest.raises(ValueError, match="invalid or has expired"):
        deps.service.confirm_password_reset(
            token="d" * 43,
            new_password="a-secure-password",
        )

    deps.repository.get_by_id_for_update.assert_not_called()
    deps.outbox.enqueue.assert_not_called()


@pytest.mark.parametrize(
    "consumed_at, expires_at",
    [
        (datetime.now(UTC), datetime.now(UTC) + timedelta(minutes=10)),
        (None, datetime.now(UTC) - timedelta(seconds=1)),
    ],
)
def test_confirm_password_reset_rejects_consumed_or_expired_token(
    recovery_dependencies,
    consumed_at,
    expires_at,
):
    deps = recovery_dependencies
    user_id = uuid.uuid4()
    user = SimpleNamespace(
        id=user_id,
        email="person@example.com",
        is_active=True,
        password_hash="old-hash",
    )
    reset_token = PasswordResetToken(
        user_id=user_id,
        token_hash=hashlib.sha256(("e" * 43).encode()).hexdigest(),
        expires_at=expires_at,
        consumed_at=consumed_at,
    )

    deps.db.scalar.side_effect = [user_id, reset_token]
    deps.repository.get_by_id_for_update.return_value = user

    with pytest.raises(ValueError, match="invalid or has expired"):
        deps.service.confirm_password_reset(
            token="e" * 43,
            new_password="a-secure-password",
        )

    assert user.password_hash == "old-hash"
    deps.db.execute.assert_not_called()
    deps.outbox.enqueue.assert_not_called()


def test_confirm_password_reset_rejects_inactive_user(
    recovery_dependencies,
):
    deps = recovery_dependencies
    user_id = uuid.uuid4()
    inactive_user = SimpleNamespace(
        id=user_id,
        email="inactive@example.com",
        is_active=False,
        password_hash="old-hash",
    )
    deps.db.scalar.return_value = user_id
    deps.repository.get_by_id_for_update.return_value = inactive_user

    with pytest.raises(ValueError, match="invalid or has expired"):
        deps.service.confirm_password_reset(
            token="f" * 43,
            new_password="a-secure-password",
        )

    assert inactive_user.password_hash == "old-hash"
    deps.outbox.enqueue.assert_not_called()
