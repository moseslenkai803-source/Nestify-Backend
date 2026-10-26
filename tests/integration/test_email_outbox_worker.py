import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.email_outbox import EmailOutbox
from app.models.employee_invitation import EmployeeInvitation
from app.models.user import User
from app.services.email_outbox_worker import (
    MAX_ATTEMPTS,
    EmailOutboxWorker,
)
from app.services.outbox_encryption import OutboxEncryptionService


@pytest.fixture
def worker_context(db_session, monkeypatch):
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(settings, "outbox_encryption_keys", {"v1": key})
    monkeypatch.setattr(settings, "outbox_active_encryption_key_version", "v1")

    user = User(
        id=uuid.uuid4(),
        email=f"outbox-admin-{uuid.uuid4()}@example.com",
        password_hash="test-hash",
        role="admin",
        is_active=True,
    )
    invitation = EmployeeInvitation(
        id=uuid.uuid4(),
        email=f"outbox-recipient-{uuid.uuid4()}@example.com",
        token_hash="a" * 64,
        employee_number=f"OUTBOX-{uuid.uuid4().hex[:12]}",
        department="Operations",
        position="Officer",
        clearances=["plate_operations"],
        invited_by_user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db_session.add(user)
    db_session.flush()

    db_session.add(invitation)
    db_session.flush()

    email_service = Mock()
    encryption_service = OutboxEncryptionService()

    def session_factory():
        # Worker transactions must be independent of the test session.
        return SessionLocal()

    def create_outbox(
        *,
        status="pending",
        attempt_count=0,
        lease_expires_at=None,
        lease_id=None,
        event_type="employee_invitation",
    ):
        payload = json.dumps(
            {
                "recipient": invitation.email,
                "invitation_url": "https://example.test/accept?token=test-token",
                "expires_at": invitation.expires_at.isoformat(),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        version, ciphertext = encryption_service.encrypt(payload)

        outbox = EmailOutbox(
            id=uuid.uuid4(),
            employee_invitation_id=invitation.id,
            event_type=event_type,
            encrypted_payload=ciphertext,
            encryption_key_version=version,
            status=status,
            attempt_count=attempt_count,
            next_attempt_at=datetime.now(UTC) - timedelta(seconds=1),
            lease_id=lease_id,
            lease_expires_at=lease_expires_at,
            created_at=datetime.now(UTC),
        )
        db_session.add(outbox)
        db_session.commit()
        return outbox

    def cleanup():
        db_session.query(EmailOutbox).filter_by(
            employee_invitation_id=invitation.id
        ).delete(synchronize_session=False)
        db_session.query(EmployeeInvitation).filter_by(
            id=invitation.id
        ).delete(synchronize_session=False)
        db_session.query(User).filter_by(id=user.id).delete(
            synchronize_session=False
        )
        db_session.commit()

    try:
        yield {
            "db": db_session,
            "invitation": invitation,
            "email_service": email_service,
            "encryption_service": encryption_service,
            "session_factory": session_factory,
            "create_outbox": create_outbox,
        }
    finally:
        cleanup()


def test_worker_sends_email_and_marks_outbox_sent(worker_context):
    context = worker_context
    outbox = context["create_outbox"]()
    worker = EmailOutboxWorker(
        session_factory=context["session_factory"],
        email_service=context["email_service"],
        encryption_service=context["encryption_service"],
    )

    assert worker.process_one() is True

    context["db"].refresh(outbox)
    assert outbox.status == "sent"
    assert outbox.attempt_count == 1
    assert outbox.sent_at is not None
    assert outbox.lease_id is None
    assert outbox.lease_expires_at is None

    context["email_service"].send_employee_invitation.assert_called_once()
    call = context["email_service"].send_employee_invitation.call_args.kwargs
    assert call["recipient"] == context["invitation"].email
    assert "token=test-token" in call["invitation_url"]


def test_worker_reschedules_failed_email_without_logging_payload(
    worker_context, caplog
):
    context = worker_context
    outbox = context["create_outbox"]()
    context["email_service"].send_employee_invitation.side_effect = (
        RuntimeError("secret token=test-token")
    )
    worker = EmailOutboxWorker(
        session_factory=context["session_factory"],
        email_service=context["email_service"],
        encryption_service=context["encryption_service"],
    )

    assert worker.process_one() is True

    context["db"].refresh(outbox)
    assert outbox.status == "pending"
    assert outbox.attempt_count == 1
    assert outbox.next_attempt_at > datetime.now(UTC)
    assert outbox.last_error == "RuntimeError"
    assert outbox.lease_id is None
    assert outbox.lease_expires_at is None
    assert "test-token" not in caplog.text
    assert "secret" not in caplog.text


def test_worker_dead_letters_expired_lease_at_attempt_limit(worker_context):
    context = worker_context
    outbox = context["create_outbox"](
        status="processing",
        attempt_count=MAX_ATTEMPTS,
        lease_id=uuid.uuid4(),
        lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    worker = EmailOutboxWorker(
        session_factory=context["session_factory"],
        email_service=context["email_service"],
        encryption_service=context["encryption_service"],
    )

    assert worker.process_one() is False

    context["db"].refresh(outbox)
    assert outbox.status == "dead_letter"
    assert outbox.attempt_count == MAX_ATTEMPTS
    assert outbox.lease_id is None
    assert outbox.lease_expires_at is None
    assert outbox.last_error == "MaximumAttemptsExceeded"
    context["email_service"].send_employee_invitation.assert_not_called()


def test_worker_dead_letters_email_failure_on_final_attempt(worker_context):
    context = worker_context
    outbox = context["create_outbox"](attempt_count=MAX_ATTEMPTS - 1)
    context["email_service"].send_employee_invitation.side_effect = (
        RuntimeError("SMTP delivery failed")
    )
    worker = EmailOutboxWorker(
        session_factory=context["session_factory"],
        email_service=context["email_service"],
        encryption_service=context["encryption_service"],
    )

    assert worker.process_one() is True

    context["db"].refresh(outbox)
    assert outbox.status == "dead_letter"
    assert outbox.attempt_count == MAX_ATTEMPTS
    assert outbox.last_error == "RuntimeError"
    assert outbox.lease_id is None
    assert outbox.lease_expires_at is None
    context["email_service"].send_employee_invitation.assert_called_once()



def test_worker_reclaims_expired_lease(worker_context):
    context = worker_context
    old_lease_id = uuid.uuid4()
    outbox = context["create_outbox"](
        status="processing",
        attempt_count=1,
        lease_id=old_lease_id,
        lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    worker = EmailOutboxWorker(
        session_factory=context["session_factory"],
        email_service=context["email_service"],
        encryption_service=context["encryption_service"],
    )

    assert worker.process_one() is True

    context["db"].refresh(outbox)
    assert outbox.status == "sent"
    assert outbox.attempt_count == 2
    assert outbox.lease_id is None
    assert outbox.lease_expires_at is None
    context["email_service"].send_employee_invitation.assert_called_once()


def test_stale_lease_cannot_overwrite_newer_worker_state(worker_context):
    context = worker_context
    current_lease_id = uuid.uuid4()
    outbox = context["create_outbox"](
        status="processing",
        attempt_count=2,
        lease_id=current_lease_id,
        lease_expires_at=datetime.now(UTC) + timedelta(seconds=60),
    )
    worker = EmailOutboxWorker(
        session_factory=context["session_factory"],
        email_service=context["email_service"],
        encryption_service=context["encryption_service"],
    )
    stale_lease_id = uuid.uuid4()

    assert worker._record_success(outbox.id, stale_lease_id) is False
    worker._record_failure(outbox.id, stale_lease_id, "RuntimeError")

    context["db"].refresh(outbox)
    assert outbox.status == "processing"
    assert outbox.lease_id == current_lease_id
    assert outbox.lease_expires_at is not None
    assert outbox.attempt_count == 2
    assert outbox.sent_at is None
    assert outbox.last_error is None

    # The current lease can still record success.
    assert worker._record_success(outbox.id, current_lease_id) is True
    context["db"].refresh(outbox)
    assert outbox.status == "sent"
    assert outbox.sent_at is not None


def test_worker_does_not_send_expired_invitation(worker_context):
    context = worker_context
    context["invitation"].expires_at = (
        datetime.now(UTC) - timedelta(seconds=1)
    )
    outbox = context["create_outbox"]()
    worker = EmailOutboxWorker(
        session_factory=context["session_factory"],
        email_service=context["email_service"],
        encryption_service=context["encryption_service"],
    )

    assert worker.process_one() is True

    context["db"].refresh(outbox)
    assert outbox.status == "dead_letter"
    assert outbox.last_error == "InvitationExpired"
    assert outbox.lease_id is None
    assert outbox.lease_expires_at is None
    context["email_service"].send_employee_invitation.assert_not_called()


def test_worker_does_not_send_redeemed_invitation(worker_context):
    context = worker_context
    context["invitation"].redeemed_at = datetime.now(UTC)
    outbox = context["create_outbox"]()
    worker = EmailOutboxWorker(
        session_factory=context["session_factory"],
        email_service=context["email_service"],
        encryption_service=context["encryption_service"],
    )

    assert worker.process_one() is True

    context["db"].refresh(outbox)
    assert outbox.status == "dead_letter"
    assert outbox.last_error == "InvitationAlreadyRedeemed"
    assert outbox.lease_id is None
    assert outbox.lease_expires_at is None
    context["email_service"].send_employee_invitation.assert_not_called()


def test_claim_skips_outbox_job_locked_by_another_session(worker_context):
    from sqlalchemy import select

    context = worker_context
    outbox = context["create_outbox"]()

    locking_session = SessionLocal()
    worker = EmailOutboxWorker(
        session_factory=context["session_factory"],
        email_service=context["email_service"],
        encryption_service=context["encryption_service"],
    )

    try:
        locked_row = locking_session.execute(
            select(EmailOutbox)
            .where(EmailOutbox.id == outbox.id)
            .with_for_update()
        ).scalar_one()

        assert locked_row.status == "pending"

        # The worker must skip the row instead of waiting for its lock.
        assert worker._claim_one() is None

        context["db"].expire_all()
        context["db"].refresh(outbox)
        assert outbox.status == "pending"
        assert outbox.attempt_count == 0

        locking_session.commit()

        # Once the lock is released, the job becomes claimable.
        claim = worker._claim_one()
        assert claim is not None
        assert claim[0] == outbox.id

        context["db"].expire_all()
        context["db"].refresh(outbox)
        assert outbox.status == "processing"
        assert outbox.attempt_count == 1
    finally:
        locking_session.rollback()
        locking_session.close()


def test_expired_lease_cannot_record_success_or_failure(worker_context):
    context = worker_context
    expired_lease_id = uuid.uuid4()
    outbox = context["create_outbox"](
        status="processing",
        attempt_count=2,
        lease_id=expired_lease_id,
        lease_expires_at=datetime.now(UTC) - timedelta(seconds=5),
    )
    worker = EmailOutboxWorker(
        session_factory=context["session_factory"],
        email_service=context["email_service"],
        encryption_service=context["encryption_service"],
    )

    assert worker._record_success(outbox.id, expired_lease_id) is False
    worker._record_failure(outbox.id, expired_lease_id, "RuntimeError")
    assert (
        worker._record_non_retryable_failure(
            outbox.id, expired_lease_id, "InvitationExpired"
        )
        is False
    )

    context["db"].refresh(outbox)
    assert outbox.status == "processing"
    assert outbox.lease_id == expired_lease_id
    assert outbox.lease_expires_at <= datetime.now(UTC)
    assert outbox.attempt_count == 2
    assert outbox.sent_at is None
    assert outbox.last_error is None
