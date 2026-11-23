import base64
from email.message import EmailMessage

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import settings


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class EmailDeliveryError(RuntimeError):
    """Raised when email delivery is unavailable or fails."""


class EmailService:
    @staticmethod
    def validate_configuration() -> None:
        required_credentials = (
            settings.gmail_client_id,
            settings.gmail_client_secret,
            settings.gmail_refresh_token,
            settings.gmail_sender_email,
        )

        if not all(
            isinstance(value, str) and value.strip()
            for value in required_credentials
        ):
            raise EmailDeliveryError(
                "Gmail API email delivery is not configured"
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

    def send_password_reset_otp(
        self,
        *,
        recipient: str,
        otp: str,
        expires_at: str,
    ) -> None:
        body = (
            "We received a request to reset your Nestify password.\n\n"
            f"Your password reset verification code is: {otp}\n\n"
            f"This code expires at {expires_at} (UTC).\n"
            "You can use this code only once. "
            "If you did not request a password reset, you can ignore this email."
        )
        self.send_email(
            recipient=recipient,
            subject="Your Nestify password reset code",
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
        """Deliver an email through the Gmail API."""
        self.validate_configuration()

        if (
            not recipient.strip()
            or not subject.strip()
            or not text_body.strip()
        ):
            raise EmailDeliveryError(
                "Recipient, subject, and text body are required"
            )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.gmail_sender_email
        message["To"] = recipient
        message.set_content(text_body)

        if html_body is not None:
            if not html_body.strip():
                raise EmailDeliveryError("HTML body cannot be empty")
            message.add_alternative(html_body, subtype="html")

        raw_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode("ascii")

        credentials = Credentials(
            token=None,
            refresh_token=settings.gmail_refresh_token,
            token_uri=GOOGLE_TOKEN_URI,
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
            scopes=[GMAIL_SEND_SCOPE],
        )

        try:
            gmail = build(
                "gmail",
                "v1",
                credentials=credentials,
                cache_discovery=False,
            )

            gmail.users().messages().send(
                userId="me",
                body={"raw": raw_message},
            ).execute()

        except Exception as exc:
            raise EmailDeliveryError(
                "Email delivery failed"
            ) from exc
