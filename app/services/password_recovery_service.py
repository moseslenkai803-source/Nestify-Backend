import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.repositories.user_repository import UserRepository
from app.services.email_outbox_enqueue_service import EmailOutboxEnqueueService


class PasswordRecoveryService:
    RESET_TOKEN_LIFETIME = timedelta(minutes=30)

    def __init__(self, db: Session):
        self.db = db
        self.user_repository = UserRepository(db)
        self.outbox = EmailOutboxEnqueueService(db)

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def request_password_reset(self, *, email: str) -> bool:
        normalized_email = self._normalize_email(email)
        user = self.user_repository.get_by_email(normalized_email)

        if user is None or not user.is_active:
            return False

        # Serialize reset requests for this account before invalidating
        # previously issued tokens and creating a replacement.
        user = self.user_repository.get_by_id_for_update(user.id)
        if user is None or not user.is_active:
            return False

        now = self._utc_now()
        self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
            .execution_options(synchronize_session=False)
        )

        raw_token = secrets.token_urlsafe(32)
        expires_at = now + self.RESET_TOKEN_LIFETIME

        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=self._hash_token(raw_token),
            expires_at=expires_at,
        )
        self.db.add(reset_token)
        self.db.flush()

        reset_url = (
            f"{settings.frontend_base_url.rstrip('/')}"
            f"/reset-password?token={quote(raw_token, safe='')}"
        )

        self.outbox.enqueue(
            event_type="password_reset",
            payload={
                "recipient": user.email,
                "reset_url": reset_url,
                "expires_at": expires_at.isoformat(),
            },
        )
        return True

    def confirm_password_reset(
        self,
        *,
        token: str,
        new_password: str,
    ) -> None:
        if not 12 <= len(new_password) <= 128:
            raise ValueError("Password must be between 12 and 128 characters")

        token_hash = self._hash_token(token)

        # Find the account first, then always acquire locks in the same order:
        # user row followed by token row. This serializes different reset
        # tokens issued for the same account.
        user_id = self.db.scalar(
            select(PasswordResetToken.user_id).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
        if user_id is None:
            raise ValueError("Password reset token is invalid or has expired")

        user = self.user_repository.get_by_id_for_update(user_id)
        if user is None or not user.is_active:
            raise ValueError("Password reset token is invalid or has expired")

        reset_token = self.db.scalar(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == token_hash)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        now = self._utc_now()
        if (
            reset_token is None
            or reset_token.user_id != user.id
            or reset_token.consumed_at is not None
            or self._as_utc(reset_token.expires_at) <= now
        ):
            raise ValueError("Password reset token is invalid or has expired")

        user.password_hash = hash_password(new_password)

        # Consume this token and invalidate every other outstanding token
        # for the same user as part of the same database transaction.
        self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
            .execution_options(synchronize_session=False)
        )

        self.outbox.enqueue(
            event_type="password_changed",
            payload={"recipient": user.email},
        )
        self.db.flush()
