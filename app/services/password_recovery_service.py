import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset_otp_challenge import (
    PasswordResetOtpChallenge,
)
from app.repositories.user_repository import UserRepository
from app.services.email_outbox_enqueue_service import EmailOutboxEnqueueService


class PasswordRecoveryService:
    OTP_LIFETIME = timedelta(minutes=10)
    OTP_RESEND_COOLDOWN = timedelta(seconds=60)
    OTP_MAX_ATTEMPTS = 5
    RESET_GRANT_LIFETIME = timedelta(minutes=5)

    def __init__(self, db: Session):
        self.db = db
        self.user_repository = UserRepository(db)
        self.outbox = EmailOutboxEnqueueService(db)

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _keyed_hash(value: str, *, purpose: str) -> str:
        pepper = settings.password_reset_otp_pepper
        if not isinstance(pepper, str) or len(pepper) < 32:
            raise RuntimeError("Password reset OTP pepper is not configured")

        message = f"nestify:{purpose}:v1:{value}".encode("utf-8")
        return hmac.new(
            pepper.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()

    def _otp_hash(self, challenge_id: uuid.UUID, otp: str) -> str:
        return self._keyed_hash(
            f"{challenge_id}:{otp}",
            purpose="password-reset-otp",
        )

    def _grant_hash(self, reset_grant: str) -> str:
        return self._keyed_hash(
            reset_grant,
            purpose="password-reset-grant",
        )

    def request_password_reset(self, *, email: str) -> bool:
        normalized_email = self._normalize_email(email)
        user = self.user_repository.get_by_email(normalized_email)

        if user is None or not user.is_active:
            return False

        # Always lock the account before locking any recovery challenge.
        user = self.user_repository.get_by_id_for_update(user.id)
        if user is None or not user.is_active:
            return False

        now = self._utc_now()

        latest_challenge = self.db.scalar(
            select(PasswordResetOtpChallenge)
            .where(PasswordResetOtpChallenge.user_id == user.id)
            .order_by(PasswordResetOtpChallenge.created_at.desc())
            .limit(1)
            .with_for_update()
        )

        if latest_challenge is not None:
            created_at = self._as_utc(latest_challenge.created_at)
            if now < created_at + self.OTP_RESEND_COOLDOWN:
                return False

        # Supersede every previously active challenge for this account.
        self.db.execute(
            update(PasswordResetOtpChallenge)
            .where(
                PasswordResetOtpChallenge.user_id == user.id,
                PasswordResetOtpChallenge.consumed_at.is_(None),
            )
            .values(consumed_at=now)
            .execution_options(synchronize_session=False)
        )

        challenge_id = uuid.uuid4()
        otp = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = now + self.OTP_LIFETIME

        challenge = PasswordResetOtpChallenge(
            id=challenge_id,
            user_id=user.id,
            otp_hash=self._otp_hash(challenge_id, otp),
            expires_at=expires_at,
            attempt_count=0,
        )
        self.db.add(challenge)
        self.db.flush()

        self.outbox.enqueue(
            event_type="password_reset_otp",
            payload={
                "recipient": user.email,
                "otp": otp,
                "expires_at": expires_at.isoformat(),
            },
        )
        return True

    def verify_password_reset_otp(
        self,
        *,
        email: str,
        otp: str,
    ) -> str | None:
        normalized_email = self._normalize_email(email)
        user = self.user_repository.get_by_email(normalized_email)

        if user is None or not user.is_active:
            return None

        user = self.user_repository.get_by_id_for_update(user.id)
        if user is None or not user.is_active:
            return None

        challenge = self.db.scalar(
            select(PasswordResetOtpChallenge)
            .where(
                PasswordResetOtpChallenge.user_id == user.id,
                PasswordResetOtpChallenge.consumed_at.is_(None),
            )
            .order_by(PasswordResetOtpChallenge.created_at.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        now = self._utc_now()
        if (
            challenge is None
            or challenge.verified_at is not None
            or self._as_utc(challenge.expires_at) <= now
            or challenge.attempt_count >= self.OTP_MAX_ATTEMPTS
        ):
            return None

        expected_hash = self._otp_hash(challenge.id, otp)
        if not hmac.compare_digest(challenge.otp_hash, expected_hash):
            challenge.attempt_count += 1
            self.db.flush()
            return None

        reset_grant = secrets.token_urlsafe(32)
        challenge.verified_at = now
        challenge.reset_grant_hash = self._grant_hash(reset_grant)
        challenge.reset_grant_expires_at = (
            now + self.RESET_GRANT_LIFETIME
        )
        self.db.flush()

        return reset_grant

    def confirm_password_reset(
        self,
        *,
        email: str,
        reset_grant: str,
        new_password: str,
    ) -> None:
        if not 12 <= len(new_password) <= 128:
            raise ValueError("Password must be between 12 and 128 characters")

        grant_hash = self._grant_hash(reset_grant)

        # Identify the account first, then lock user followed by challenge.
        candidate = self.db.scalar(
            select(PasswordResetOtpChallenge).where(
                PasswordResetOtpChallenge.reset_grant_hash == grant_hash
            )
        )
        if candidate is None:
            raise ValueError("Password reset grant is invalid or has expired")

        user = self.user_repository.get_by_id_for_update(candidate.user_id)
        if (
            user is None
            or not user.is_active
            or self._normalize_email(user.email) != self._normalize_email(email)
        ):
            raise ValueError("Password reset grant is invalid or has expired")

        challenge = self.db.scalar(
            select(PasswordResetOtpChallenge)
            .where(PasswordResetOtpChallenge.id == candidate.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        now = self._utc_now()
        if (
            challenge is None
            or challenge.user_id != user.id
            or challenge.consumed_at is not None
            or challenge.verified_at is None
            or challenge.reset_grant_hash is None
            or not hmac.compare_digest(
                challenge.reset_grant_hash,
                grant_hash,
            )
            or challenge.reset_grant_expires_at is None
            or self._as_utc(challenge.reset_grant_expires_at) <= now
        ):
            raise ValueError("Password reset grant is invalid or has expired")

        user.password_hash = hash_password(new_password)
        user.token_version += 1
        challenge.consumed_at = now

        self.outbox.enqueue(
            event_type="password_changed",
            payload={"recipient": user.email},
        )
        self.db.flush()
