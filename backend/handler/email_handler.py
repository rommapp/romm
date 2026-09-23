"""Email deliveries over the SMTP server the SMTP_* settings describe."""

import smtplib
import socket
import ssl
from email.message import EmailMessage
from typing import Final

import config

TIMEOUT_SECONDS: Final = 30


class EmailError(RuntimeError):
    """Email isn't set up, or the SMTP server refused the message."""


def _one_line(text: str) -> str:
    # A header can't carry a line break, and a title from the API may hold one.
    return " ".join(text.split())


def build_message(to: str, subject: str, text: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = config.SMTP_FROM
    message["To"] = to
    message["Subject"] = _one_line(subject)
    message.set_content(text)
    return message


def send_email(to: str, subject: str, text: str) -> None:
    """Send a plain-text email, blocking until the server takes it.

    Raises:
        EmailError: Email isn't set up, or the server refused the message.
    """
    if not config.EMAIL_ENABLED:
        raise EmailError("Email isn't set up on this server")

    message = build_message(to, subject, text)
    context = ssl.create_default_context()
    # smtplib otherwise greets with socket.getfqdn(), a DNS lookup that can
    # stall for seconds, and in a container it names the same host anyway.
    local_hostname = socket.gethostname()
    try:
        if config.SMTP_SECURITY == "tls":
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(
                config.SMTP_HOST,
                config.SMTP_PORT,
                local_hostname=local_hostname,
                timeout=TIMEOUT_SECONDS,
                context=context,
            )
        else:
            smtp = smtplib.SMTP(
                config.SMTP_HOST,
                config.SMTP_PORT,
                local_hostname=local_hostname,
                timeout=TIMEOUT_SECONDS,
            )
        with smtp:
            if config.SMTP_SECURITY == "starttls":
                smtp.starttls(context=context)
            if config.SMTP_USERNAME:
                smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailError(f"The SMTP server refused the message: {exc}") from exc
