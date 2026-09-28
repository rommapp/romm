from unittest.mock import MagicMock

import pytest
from fakeredis import FakeRedis

from handler.auth import auth_handler, base_handler
from handler.email_handler import EmailError


@pytest.fixture(autouse=True)
def redis(mocker):
    fake = FakeRedis(version=7)
    mocker.patch.object(base_handler, "redis_client", fake)
    return fake


@pytest.fixture
def sent(mocker):
    mocker.patch.object(base_handler, "EMAIL_ENABLED", True)
    mocker.patch.object(
        base_handler, "get_public_base_url", return_value="https://romm.example.com"
    )
    return mocker.patch.object(base_handler, "send_email")


@pytest.fixture
def logged(mocker):
    return mocker.patch.object(base_handler, "log")


def _user(email: str | None = "player@example.com") -> MagicMock:
    user = MagicMock(id=7, email=email)
    user.username = "player"
    return user


def _logged_link(logged) -> bool:
    return any("Reset link:" in str(c.args[0]) for c in logged.info.call_args_list)


def test_emails_a_link_built_from_the_base_url(sent, logged, redis):
    auth_handler.send_password_reset_link(_user())

    to, subject, text = sent.call_args.args
    assert to == "player@example.com"
    assert subject == "Reset your RomM password"
    assert "https://romm.example.com/reset-password?token=" in text
    assert not _logged_link(logged)
    assert len(redis.keys("reset-jti:*")) == 1


def test_logs_the_link_for_a_user_without_an_address(sent, logged):
    auth_handler.send_password_reset_link(_user(email=None))

    sent.assert_not_called()
    assert _logged_link(logged)


def test_logs_the_link_without_a_shareable_base_url(sent, logged, mocker):
    mocker.patch.object(base_handler, "get_public_base_url", return_value=None)

    auth_handler.send_password_reset_link(_user())

    sent.assert_not_called()
    assert _logged_link(logged)


def test_logs_the_link_when_the_mail_server_refuses(sent, logged):
    sent.side_effect = EmailError("The SMTP server refused the message")

    auth_handler.send_password_reset_link(_user())

    logged.error.assert_called_once()
    assert _logged_link(logged)


def test_a_second_request_within_a_minute_sends_nothing(sent, logged, redis):
    auth_handler.send_password_reset_link(_user())
    auth_handler.send_password_reset_link(_user())

    sent.assert_called_once()
    assert len(redis.keys("reset-jti:*")) == 1
