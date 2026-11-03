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
        self.validate_configuration()

        message = EmailMessage()
        message["Subject"] = "Your Nestify employee invitation"
        message["From"] = settings.smtp_from_email
        message["To"] = recipient
        message.set_content(
            "You have been invited to join Nestify as an employee.\n\n"
            f"Accept your invitation using this link:\n{invitation_url}\n\n"
            f"This invitation expires at {expires_at} (UTC).\n"
            "If you were not expecting this invitation, you can ignore this email."
        )

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
            raise EmailDeliveryError("Invitation email delivery failed") from exc

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
