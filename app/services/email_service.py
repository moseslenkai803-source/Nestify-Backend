import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


class EmailDeliveryError(RuntimeError):
    """Raised when email delivery is unavailable or fails."""


class EmailService:
    @staticmethod
    def validate_configuration() -> None:
        if not (
            settings.smtp_host
            and settings.smtp_from_email
            and (
                bool(settings.smtp_username)
                == bool(settings.smtp_password)
            )
        ):
            raise EmailDeliveryError("Email delivery is not configured")

        if settings.smtp_use_ssl and settings.smtp_starttls:
            raise EmailDeliveryError(
                "Configure either implicit SSL or STARTTLS, not both"
            )

        is_development = (
            settings.environment.strip().lower() == "development"
        )
        if not is_development and not (
            settings.smtp_use_ssl or settings.smtp_starttls
        ):
            raise EmailDeliveryError(
                "Non-development email delivery requires encrypted SMTP"
            )

    @classmethod
    def is_configured(cls) -> bool:
        try:
            cls.validate_configuration()
        except EmailDeliveryError:
            return False
        return True

    def send_employee_invitation(
        self,
        *,
        recipient: str,
        invitation_url: str,
        expires_at: str,
    ) -> None:
        body = (
            "You have been invited to join Nestify as an employee.\n\n"
            f"Accept your invitation using this link:\n{invitation_url}\n\n"
            f"This invitation expires at {expires_at} (UTC).\n"
            "If you were not expecting this invitation, you can ignore this email."
        )

        self.send_email(
            recipient=recipient,
            subject="Your Nestify employee invitation",
            text_body=body,
        )

    def send_password_reset(
        self,
        *,
        recipient: str,
        reset_url: str,
        expires_at: str,
    ) -> None:
        body = (
            "We received a request to reset your Nestify password.\n\n"
            f"Reset your password using this link:\n{reset_url}\n\n"
            f"This link expires at {expires_at} (UTC).\n"
            "If you did not request a password reset, you can ignore this email."
        )
        self.send_email(
            recipient=recipient,
            subject="Reset your Nestify password",
            text_body=body,
        )

    def send_password_changed(self, *, recipient: str) -> None:
        body = (
            "Your Nestify password was changed.\n\n"
            "If you did not make this change, contact Nestify through "
            "its official support channels."
        )
        self.send_email(
            recipient=recipient,
            subject="Your Nestify password was changed",
            text_body=body,
        )

    def send_email(
        self,
        *,
        recipient: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
    ) -> None:
        """Deliver a generic email using the configured SMTP transport."""
        self.validate_configuration()

        if not recipient.strip() or not subject.strip() or not text_body.strip():
            raise EmailDeliveryError(
                "Recipient, subject, and text body are required"
            )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.smtp_from_email
        message["To"] = recipient
        message.set_content(text_body)

        if html_body is not None:
            if not html_body.strip():
                raise EmailDeliveryError("HTML body cannot be empty")
            message.add_alternative(html_body, subtype="html")

        context = ssl.create_default_context()

        try:
            if settings.smtp_use_ssl:
                with smtplib.SMTP_SSL(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=15,
                    context=context,
                ) as server:
                    self._authenticate_and_send(server, message)
            else:
                with smtplib.SMTP(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=15,
                ) as server:
                    server.ehlo()
                    if settings.smtp_starttls:
                        server.starttls(context=context)
                        server.ehlo()
                    self._authenticate_and_send(server, message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError("Email delivery failed") from exc

    @staticmethod
    def _authenticate_and_send(
        server: smtplib.SMTP,
        message: EmailMessage,
    ) -> None:
        if settings.smtp_username:
            if not settings.smtp_password:
                raise EmailDeliveryError(
                    "SMTP password is required when a username is configured"
                )
            server.login(settings.smtp_username, settings.smtp_password)

        server.send_message(message)
