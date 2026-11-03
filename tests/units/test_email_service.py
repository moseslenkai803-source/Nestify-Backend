import smtplib
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.services.email_service import EmailDeliveryError, EmailService


@pytest.fixture
def smtp_settings(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_username", "mailer@example.com")
    monkeypatch.setattr(settings, "smtp_password", "test-password")
    monkeypatch.setattr(settings, "smtp_from_email", "mailer@example.com")
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    monkeypatch.setattr(settings, "smtp_starttls", True)


def test_email_service_reports_missing_configuration(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", None)
    monkeypatch.setattr(settings, "smtp_from_email", None)

    assert EmailService.is_configured() is False

    with pytest.raises(EmailDeliveryError, match="not configured"):
        EmailService().send_employee_invitation(
            recipient="employee@example.com",
            invitation_url="https://example.com/invite?token=test-token",
            expires_at="2026-10-12T12:00:00+00:00",
        )


def test_sends_invitation_using_starttls(smtp_settings):
    smtp = MagicMock()
    server = smtp.return_value.__enter__.return_value

    with patch("app.services.email_service.smtplib.SMTP", smtp):
        EmailService().send_employee_invitation(
            recipient="employee@example.com",
            invitation_url="https://example.com/invite?token=test-token",
            expires_at="2026-10-12T12:00:00+00:00",
        )

    smtp.assert_called_once_with(
        "smtp.example.com",
        587,
        timeout=15,
    )
    server.starttls.assert_called_once()
    server.login.assert_called_once_with(
        "mailer@example.com",
        "test-password",
    )
    server.send_message.assert_called_once()

    message = server.send_message.call_args.args[0]
    assert message["To"] == "employee@example.com"
    assert "test-token" in message.get_content()
    assert "2026-10-12T12:00:00+00:00" in message.get_content()


def test_smtp_failure_raises_delivery_error(smtp_settings):
    smtp = MagicMock()
    smtp.return_value.__enter__.side_effect = smtplib.SMTPConnectError(
        421, b"Connection refused"
    )

    with patch("app.services.email_service.smtplib.SMTP", smtp):
        with pytest.raises(EmailDeliveryError, match="delivery failed"):
            EmailService().send_employee_invitation(
                recipient="employee@example.com",
                invitation_url="https://example.com/invite?token=test-token",
                expires_at="2026-10-12T12:00:00+00:00",
            )


def test_conflicting_ssl_settings_are_rejected(smtp_settings, monkeypatch):
    monkeypatch.setattr(settings, "smtp_use_ssl", True)
    monkeypatch.setattr(settings, "smtp_starttls", True)

    with pytest.raises(EmailDeliveryError, match="not both"):
        EmailService().send_employee_invitation(
            recipient="employee@example.com",
            invitation_url="https://example.com/invite?token=test-token",
            expires_at="2026-10-12T12:00:00+00:00",
        )

def test_email_service_rejects_incomplete_smtp_credentials(
    smtp_settings, monkeypatch
):
    monkeypatch.setattr(settings, "smtp_password", None)

    assert EmailService.is_configured() is False

    with pytest.raises(EmailDeliveryError, match="not configured"):
        EmailService().send_employee_invitation(
            recipient="employee@example.com",
            invitation_url="https://example.com/invite?token=test-token",
            expires_at="2026-10-12T12:00:00+00:00",
        )


def test_production_rejects_unencrypted_smtp(smtp_settings, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    monkeypatch.setattr(settings, "smtp_starttls", False)

    with pytest.raises(EmailDeliveryError, match="requires encrypted SMTP"):
        EmailService().send_employee_invitation(
            recipient="employee@example.com",
            invitation_url="https://example.com/invite?token=test-token",
            expires_at="2026-10-12T12:00:00+00:00",
        )




def test_is_configured_rejects_conflicting_transport(smtp_settings, monkeypatch):
    monkeypatch.setattr(settings, "smtp_use_ssl", True)
    monkeypatch.setattr(settings, "smtp_starttls", True)

    assert EmailService.is_configured() is False


def test_is_configured_rejects_unencrypted_production(
    smtp_settings, monkeypatch
):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    monkeypatch.setattr(settings, "smtp_starttls", False)

    assert EmailService.is_configured() is False


@pytest.mark.parametrize("environment", ["staging", "test"])
def test_non_development_rejects_unencrypted_smtp(
    smtp_settings, monkeypatch, environment
):
    monkeypatch.setattr(settings, "environment", environment)
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    monkeypatch.setattr(settings, "smtp_starttls", False)

    with pytest.raises(
        EmailDeliveryError,
        match="Non-development email delivery requires encrypted SMTP",
    ):
        EmailService().send_employee_invitation(
            recipient="employee@example.com",
            invitation_url="https://example.com/invite?token=test-token",
            expires_at="2026-10-12T12:00:00+00:00",
        )
