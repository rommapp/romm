from unittest.mock import MagicMock

import pytest

from handler import email_handler
from handler.email_handler import EmailError, build_message, send_email


@pytest.fixture
def smtp_settings(mocker):
    def configure(security: str = "starttls", username: str = "romm"):
        for name, value in {
            "EMAIL_ENABLED": True,
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": 587,
            "SMTP_FROM": "romm@example.com",
            "SMTP_USERNAME": username,
            "SMTP_PASSWORD": "hunter2",
            "SMTP_SECURITY": security,
        }.items():
            mocker.patch.object(email_handler.config, name, value)

    return configure


def test_a_subject_is_kept_to_one_line(smtp_settings):
    smtp_settings()

    message = build_message("a@example.com", "Scan\r\nfailed", "body")

    assert message["Subject"] == "Scan failed"
    assert message["From"] == "romm@example.com"


@pytest.mark.parametrize(
    "security,client,starttls",
    [("starttls", "SMTP", True), ("none", "SMTP", False), ("tls", "SMTP_SSL", False)],
)
def test_speaks_the_configured_security(
    mocker, smtp_settings, security, client, starttls
):
    smtp_settings(security=security)
    server = MagicMock()
    connect = mocker.patch.object(email_handler.smtplib, client, return_value=server)

    send_email("a@example.com", "Hi", "There")

    connect.assert_called_once()
    assert server.starttls.called is starttls
    server.login.assert_called_once_with("romm", "hunter2")
    server.send_message.assert_called_once()


def test_logs_in_only_with_a_username(mocker, smtp_settings):
    smtp_settings(username="")
    server = MagicMock()
    mocker.patch.object(email_handler.smtplib, "SMTP", return_value=server)

    send_email("a@example.com", "Hi", "There")

    server.login.assert_not_called()


def test_a_refused_message_is_an_email_error(mocker, smtp_settings):
    smtp_settings()
    mocker.patch.object(
        email_handler.smtplib, "SMTP", side_effect=ConnectionRefusedError("refused")
    )

    with pytest.raises(EmailError, match="refused"):
        send_email("a@example.com", "Hi", "There")


def test_nothing_goes_out_without_a_server(mocker):
    mocker.patch.object(email_handler.config, "EMAIL_ENABLED", False)

    with pytest.raises(EmailError, match="isn't set up"):
        send_email("a@example.com", "Hi", "There")
