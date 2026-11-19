import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_outbox import EmailOutbox
from app.services.outbox_encryption import (
    OutboxEncryptionError,
    OutboxEncryptionService,
)


class EmailOutboxEnqueueService:
    """Encrypt and persist an email event in the caller's transaction."""

    def __init__(
        self,
        db: Session,
        encryption_service: OutboxEncryptionService | None = None,
    ) -> None:
        self.db = db
        self.encryption_service = (
            encryption_service or OutboxEncryptionService()
        )

    def enqueue(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        employee_invitation_id: uuid.UUID | None = None,
    ) -> EmailOutbox:
        normalized_event_type = event_type.strip()

        if not normalized_event_type:
            raise ValueError("Email outbox event type is required")

        if not isinstance(payload, dict) or not payload:
            raise ValueError("Email outbox payload must be a non-empty object")

        try:
            serialized_payload = json.dumps(
                payload,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("Email outbox payload must be JSON serializable") from exc

        key_version, encrypted_payload = self.encryption_service.encrypt(
            serialized_payload
        )

        outbox = EmailOutbox(
            employee_invitation_id=employee_invitation_id,
            event_type=normalized_event_type,
            encrypted_payload=encrypted_payload,
            encryption_key_version=key_version,
        )
        self.db.add(outbox)
        self.db.flush()

        return outbox


__all__ = ["EmailOutboxEnqueueService", "OutboxEncryptionError"]
