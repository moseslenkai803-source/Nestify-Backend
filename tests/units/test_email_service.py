import base64
from email import message_from_bytes
from email.policy import default
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.services.email_service import (
    GMAIL_SEND_SCOPE,
    EmailDeliveryError,
    EmailService,
)


@pytest.fixture
def gmail_settings(monkeypatch):
    monkeypatch.setattr(
        settings, "gmail_client_id", "test-client-id"
    )
    monkeypatch.setattr(
        settings, "gmail_client_secret", "test-client-secret"
    )
    monkeypatch.setattr(
        settings, "gmail_refresh_token", "test-refresh-token"
    )
    monkeypatch.setattr(
        settings, "gmail_sender_email", "mailer@example.com"
    )


def mock_gmail_api():
    gmail = MagicMock()
    return gmail


def decoded_message(gmail):
    raw = gmail.users.return_value.messages.return_value.send.call_args.kwargs[
        "body"
    ]["raw"]
    decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
    return message_from_bytes(decoded, policy=default)


def test_email_service_reports_missing_configuration(monkeypatch):
    monkeypatch.setattr(settings, "gmail_client_id", None)

    assert EmailService.is_configured() is False

    with pytest.raises(EmailDeliveryError, match="not configured"):
        EmailService().send_employee_invitation(
            recipient="employee@example.com",
            invitation_url="https://example.com/invite?token=test-token",
            expires_at="2026-10-12T12:00:00+00:00",
        )


@pytest.mark.parametrize(
    "missing_setting",
    [
        "gmail_client_id",
        "gmail_client_secret",
        "gmail_refresh_token",
        "gmail_sender_email",
    ],
)
def test_configuration_requires_all_gmail_credentials(
    gmail_settings, monkeypatch, missing_setting
):
    monkeypatch.setattr(settings, missing_setting, " ")

    assert EmailService.is_configured() is False

    with pytest.raises(EmailDeliveryError, match="not configured"):
        EmailService.validate_configuration()


def test_is_configured_returns_true_with_all_credentials(gmail_settings):
    assert EmailService.is_configured() is True


def test_sends_employee_invitation_through_gmail_api(gmail_settings):
    gmail = mock_gmail_api()

    with patch("app.services.email_service.build", return_value=gmail) as build:
        EmailService().send_employee_invitation(
            recipient="employee@example.com",
            invitation_url="https://example.com/invite?token=test-token",
            expires_at="2026-10-12T12:00:00+00:00",
        )

    build.assert_called_once_with(
        "gmail",
        "v1",
        credentials=build.call_args.kwargs["credentials"],
        cache_discovery=False,
    )
    assert build.call_args.kwargs["credentials"].refresh_token == (
        "test-refresh-token"
    )
    assert build.call_args.kwargs["credentials"].scopes == [
        GMAIL_SEND_SCOPE
    ]

    gmail.users.return_value.messages.return_value.send.assert_called_once()
    send_call = gmail.users.return_value.messages.return_value.send.call_args
    assert send_call.kwargs["userId"] == "me"

    message = decoded_message(gmail)
    body = message.get_content()

    assert message["To"] == "employee@example.com"
    assert message["From"] == "mailer@example.com"
    assert message["Subject"] == "Your Nestify employee invitation"
    assert "test-token" in body
    assert "2026-10-12T12:00:00+00:00" in body
    assert "\n" in body
    assert r"\n" not in body


def test_sends_generic_text_email_through_gmail_api(gmail_settings):
    gmail = mock_gmail_api()

    with patch("app.services.email_service.build", return_value=gmail):
        EmailService().send_email(
            recipient="user@example.com",
            subject="Password changed",
            text_body="Your Nestify password was changed.",
        )

    message = decoded_message(gmail)
    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Password changed"
    assert message.get_content() == "Your Nestify password was changed.\n"


def test_sends_generic_email_with_html_alternative(gmail_settings):
    gmail = mock_gmail_api()

    with patch("app.services.email_service.build", return_value=gmail):
        EmailService().send_email(
            recipient="user@example.com",
            subject="Reset your password",
            text_body="Use the link in this email to reset your password.",
            html_body="<p>Reset your <strong>Nestify</strong> password.</p>",
        )

    message = decoded_message(gmail)
    assert message.get_content_type() == "multipart/alternative"

    parts = list(message.iter_parts())
    assert len(parts) == 2
    assert parts[0].get_content_type() == "text/plain"
    assert parts[1].get_content_type() == "text/html"
    assert "Nestify" in parts[1].get_content()


@pytest.mark.parametrize(
    "overrides",
    [
        {"recipient": " ", "subject": "Subject", "text_body": "Body"},
        {"recipient": "user@example.com", "subject": " ", "text_body": "Body"},
        {"recipient": "user@example.com", "subject": "Subject", "text_body": " "},
    ],
)
def test_generic_email_rejects_missing_required_content(
    gmail_settings, overrides
):
    with pytest.raises(EmailDeliveryError, match="required"):
        EmailService().send_email(**overrides)


def test_generic_email_rejects_empty_html_body(gmail_settings):
    with pytest.raises(EmailDeliveryError, match="HTML body"):
        EmailService().send_email(
            recipient="user@example.com",
            subject="Subject",
            text_body="Body",
            html_body=" ",
        )


def test_gmail_api_failure_raises_delivery_error(gmail_settings):
    gmail = mock_gmail_api()
    gmail.users.return_value.messages.return_value.send.return_value.execute.side_effect = (
        RuntimeError("simulated Gmail API failure")
    )

    with patch("app.services.email_service.build", return_value=gmail):
        with pytest.raises(EmailDeliveryError, match="Email delivery failed"):
            EmailService().send_email(
                recipient="user@example.com",
                subject="Subject",
                text_body="Body",
            )


def test_sends_password_reset_email_with_link_and_expiry(gmail_settings):
    gmail = mock_gmail_api()
    reset_url = "https://example.com/reset?token=test-reset-token"

    with patch("app.services.email_service.build", return_value=gmail):
        EmailService().send_password_reset(
            recipient="user@example.com",
            reset_url=reset_url,
            expires_at="2026-11-15T13:00:00+00:00",
        )

    message = decoded_message(gmail)
    body = message.get_content()

    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Reset your Nestify password"
    assert reset_url in body
    assert "2026-11-15T13:00:00+00:00" in body
    assert "If you did not request a password reset" in body
    assert "\n" in body
    assert r"\n" not in body


def test_sends_password_changed_notification(gmail_settings):
    gmail = mock_gmail_api()

    with patch("app.services.email_service.build", return_value=gmail):
        EmailService().send_password_changed(
            recipient="user@example.com",
        )

    message = decoded_message(gmail)
    body = message.get_content()

    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Your Nestify password was changed"
    assert "Your Nestify password was changed." in body
    assert "official support channels" in body
    assert "\n" in body
    assert r"\n" not in body
