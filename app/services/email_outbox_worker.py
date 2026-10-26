import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Callable

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.email_outbox import EmailOutbox
from app.models.employee_invitation import EmployeeInvitation
from app.services.email_service import EmailService
from app.services.outbox_encryption import OutboxEncryptionService


logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
LEASE_DURATION = timedelta(seconds=60)
INITIAL_RETRY_DELAY = timedelta(seconds=30)
MAX_RETRY_DELAY = timedelta(hours=1)


class EmailOutboxWorker:
    """Claims and delivers encrypted email outbox jobs."""

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        email_service: EmailService | None = None,
        encryption_service: OutboxEncryptionService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.email_service = email_service or EmailService()
        self.encryption_service = (
            encryption_service or OutboxEncryptionService()
        )

    def process_one(self) -> bool:
        """Process one eligible job; return False when no job is available."""
        job = self._claim_one()
        if job is None:
            return False

        (
            job_id,
            lease_id,
            key_version,
            ciphertext,
            event_type,
            invitation_id,
        ) = job

        try:
            if event_type != "employee_invitation":
                raise ValueError("Unsupported outbox event type")

            payload_bytes = self.encryption_service.decrypt(
                key_version,
                ciphertext,
            )
            payload = json.loads(payload_bytes.decode("utf-8"))

            recipient = payload["recipient"]
            invitation_url = payload["invitation_url"]
            expires_at = payload["expires_at"]

            if not all(
                isinstance(value, str) and value.strip()
                for value in (recipient, invitation_url, expires_at)
            ):
                raise ValueError("Invalid invitation payload")

            invalid_reason = self._invitation_delivery_block_reason(
                invitation_id
            )
            if invalid_reason is not None:
                self._record_non_retryable_failure(
                    job_id, lease_id, invalid_reason
                )
                logger.info(
                    "Email outbox job suppressed: job_id=%s reason=%s",
                    job_id,
                    invalid_reason,
                )
                return True

            self.email_service.send_employee_invitation(
                recipient=recipient,
                invitation_url=invitation_url,
                expires_at=expires_at,
            )
        except Exception as exc:
            # Persist only the exception type, never payloads, URLs, tokens,
            # recipient addresses, or raw exception messages.
            self._record_failure(job_id, lease_id, type(exc).__name__)
            logger.warning(
                "Email outbox job failed: job_id=%s error_type=%s",
                job_id,
                type(exc).__name__,
            )
            return True

        if self._record_success(job_id, lease_id):
            logger.info("Email outbox job sent: job_id=%s", job_id)
        else:
            logger.warning(
                "Email outbox delivery completed but lease was lost "
                "before status update: job_id=%s",
                job_id,
            )
        return True

    def _claim_one(
        self,
    ) -> tuple[uuid.UUID, uuid.UUID, str, str, str, uuid.UUID] | None:
        now = datetime.now(UTC)
        lease_id = uuid.uuid4()

        with self.session_factory() as db:
            # A worker may crash on its final permitted attempt. Once that
            # lease expires, do not keep reclaiming the exhausted job.
            db.execute(
                update(EmailOutbox)
                .where(
                    EmailOutbox.status == "processing",
                    EmailOutbox.lease_expires_at <= now,
                    EmailOutbox.attempt_count >= MAX_ATTEMPTS,
                )
                .values(
                    status="dead_letter",
                    lease_id=None,
                    lease_expires_at=None,
                    last_error="MaximumAttemptsExceeded",
                )
            )

            statement = (
                select(EmailOutbox)
                .where(
                    EmailOutbox.attempt_count < MAX_ATTEMPTS,
                    or_(
                        (
                            (EmailOutbox.status == "pending")
                            & (EmailOutbox.next_attempt_at <= now)
                        ),
                        (
                            (EmailOutbox.status == "processing")
                            & (EmailOutbox.lease_expires_at <= now)
                        ),
                    )
                )
                .order_by(
                    EmailOutbox.next_attempt_at,
                    EmailOutbox.created_at,
                )
                .limit(1)
                .with_for_update(skip_locked=True)
            )

            outbox = db.execute(statement).scalar_one_or_none()
            if outbox is None:
                db.commit()
                return None

            outbox.status = "processing"
            outbox.lease_id = lease_id
            outbox.lease_expires_at = now + LEASE_DURATION
            outbox.attempt_count += 1
            outbox.last_error = None

            result = (
                outbox.id,
                lease_id,
                outbox.encryption_key_version,
                outbox.encrypted_payload,
                outbox.event_type,
                outbox.employee_invitation_id,
            )

            # Commit the claim before doing network I/O.
            db.commit()
            return result

    def _invitation_delivery_block_reason(
        self,
        invitation_id: uuid.UUID,
    ) -> str | None:
        """Return a safe reason when an invitation must not be emailed."""
        now = datetime.now(UTC)

        with self.session_factory() as db:
            invitation = db.get(EmployeeInvitation, invitation_id)

            if invitation is None:
                return "InvitationMissing"
            if invitation.redeemed_at is not None:
                return "InvitationAlreadyRedeemed"

            expires_at = invitation.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            else:
                expires_at = expires_at.astimezone(UTC)

            if expires_at <= now:
                return "InvitationExpired"

        return None

    def _record_non_retryable_failure(
        self,
        job_id: uuid.UUID,
        lease_id: uuid.UUID,
        reason: str,
    ) -> bool:
        """Dead-letter a job only if this worker still owns its lease."""
        now = datetime.now(UTC)

        with self.session_factory() as db:
            result = db.execute(
                update(EmailOutbox)
                .where(
                    EmailOutbox.id == job_id,
                    EmailOutbox.status == "processing",
                    EmailOutbox.lease_id == lease_id,
                    EmailOutbox.lease_expires_at > now,
                )
                .values(
                    status="dead_letter",
                    lease_id=None,
                    lease_expires_at=None,
                    last_error=reason[:500],
                )
            )
            db.commit()
            return result.rowcount == 1

    def _record_success(
        self,
        job_id: uuid.UUID,
        lease_id: uuid.UUID,
    ) -> bool:
        now = datetime.now(UTC)

        with self.session_factory() as db:
            result = db.execute(
                update(EmailOutbox)
                .where(
                    EmailOutbox.id == job_id,
                    EmailOutbox.status == "processing",
                    EmailOutbox.lease_id == lease_id,
                    EmailOutbox.lease_expires_at > now,
                )
                .values(
                    status="sent",
                    sent_at=now,
                    lease_id=None,
                    lease_expires_at=None,
                    last_error=None,
                )
            )
            db.commit()
            return result.rowcount == 1

    def _record_failure(
        self,
        job_id: uuid.UUID,
        lease_id: uuid.UUID,
        error_type: str,
    ) -> None:
        now = datetime.now(UTC)

        with self.session_factory() as db:
            outbox = db.execute(
                select(EmailOutbox).where(
                    EmailOutbox.id == job_id,
                    EmailOutbox.status == "processing",
                    EmailOutbox.lease_id == lease_id,
                    EmailOutbox.lease_expires_at > now,
                )
            ).scalar_one_or_none()

            # A newer worker may already have reclaimed this job.
            if outbox is None:
                return

            if outbox.attempt_count >= MAX_ATTEMPTS:
                next_status = "dead_letter"
                next_attempt_at = outbox.next_attempt_at
            else:
                next_status = "pending"
                delay_seconds = min(
                    INITIAL_RETRY_DELAY.total_seconds()
                    * (2 ** (outbox.attempt_count - 1)),
                    MAX_RETRY_DELAY.total_seconds(),
                )
                next_attempt_at = now + timedelta(
                    seconds=delay_seconds
                )

            db.execute(
                update(EmailOutbox)
                .where(
                    EmailOutbox.id == job_id,
                    EmailOutbox.status == "processing",
                    EmailOutbox.lease_id == lease_id,
                    EmailOutbox.lease_expires_at > now,
                )
                .values(
                    status=next_status,
                    next_attempt_at=next_attempt_at,
                    lease_id=None,
                    lease_expires_at=None,
                    last_error=error_type[:500],
                )
            )
            db.commit()
