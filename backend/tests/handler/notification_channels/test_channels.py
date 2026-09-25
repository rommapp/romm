from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from handler.email_handler import EmailError
from handler.notification_channels import channels
from handler.notification_channels.channels import (
    ChannelError,
    confirm_channel,
    create_channel,
    resend_code,
    send_sample,
    update_channel,
)
from handler.notification_channels.config import read_config, seal_config
from handler.notification_channels.confirmation import CodeCooldownError
from models.notification_channel import (
    NotificationChannelMinLevel,
    NotificationChannelType,
)
from models.user import Role

ADMIN = MagicMock(id=1, role=Role.ADMIN)
USER = MagicMock(id=2, role=Role.USER)
DISCORD = {"webhook_id": "1234567890", "webhook_token": "abcdefghijklmnop"}


@pytest.fixture
def db(mocker):
    handler = mocker.patch.object(channels, "db_notification_channel_handler")
    handler.add_channel.side_effect = lambda channel, limit: channel
    handler.update_channel.side_effect = lambda _id, _user, changes: MagicMock(
        **changes
    )
    return handler


@pytest.fixture
def email_on(mocker):
    mocker.patch.object(channels, "EMAIL_ENABLED", True)


@pytest.fixture
def issue(mocker):
    return mocker.patch.object(channels, "issue_code", AsyncMock())


def _stored(type=NotificationChannelType.WEBHOOK, confirmed=True, **config):
    return MagicMock(
        id=4,
        user_id=USER.id,
        type=type,
        enabled=True,
        confirmed_at=datetime.now(timezone.utc) if confirmed else None,
        config=seal_config(config),  # type: ignore[arg-type]
    )


class TestCreate:
    async def test_a_webhook_is_ready_at_once(self, db):
        channel = await create_channel(
            USER,
            NotificationChannelType.WEBHOOK,
            "Hooks",
            NotificationChannelMinLevel.WARNING,
            None,
            url="https://hooks.example.com/romm",
        )

        assert channel.confirmed_at is not None
        assert read_config(channel.config) == {
            "url": "https://hooks.example.com/romm",
            "secret": None,
        }

    async def test_an_admin_forwards_through_apprise(self, db):
        channel = await create_channel(
            ADMIN,
            NotificationChannelType.APPRISE,
            "Phone",
            NotificationChannelMinLevel.INFO,
            None,
            service="ntfy",
            fields={"targets": ["romm"]},
        )

        assert channel.confirmed_at is not None
        assert read_config(channel.config) == {
            "service": "ntfy",
            "fields": {"targets": ["romm"]},
        }

    async def test_a_user_may_not_use_apprise(self, db):
        with pytest.raises(ChannelError, match="Only admins"):
            await create_channel(
                USER,
                NotificationChannelType.APPRISE,
                "Phone",
                NotificationChannelMinLevel.INFO,
                None,
                service="ntfy",
                fields={"targets": ["romm"]},
            )

        db.add_channel.assert_not_called()

    async def test_fields_apprise_cannot_use_are_refused(self, db):
        with pytest.raises(ChannelError, match="needs Webhook Token"):
            await create_channel(
                ADMIN,
                NotificationChannelType.APPRISE,
                "Discord",
                NotificationChannelMinLevel.INFO,
                None,
                service="discord",
                fields={"webhook_id": "1234567890"},
            )

    async def test_a_user_stays_off_the_local_network(self, db):
        with pytest.raises(ChannelError):
            await create_channel(
                USER,
                NotificationChannelType.WEBHOOK,
                "LAN",
                NotificationChannelMinLevel.INFO,
                None,
                url="http://192.168.1.2/hook",
            )

    async def test_an_admin_may_reach_it(self, db):
        await create_channel(
            ADMIN,
            NotificationChannelType.WEBHOOK,
            "LAN",
            NotificationChannelMinLevel.INFO,
            None,
            url="http://192.168.1.2/hook",
        )

    async def test_there_is_a_limit(self, db):
        db.add_channel.side_effect = None
        db.add_channel.return_value = None

        with pytest.raises(ChannelError, match="at most"):
            await create_channel(
                USER,
                NotificationChannelType.WEBHOOK,
                "One more",
                NotificationChannelMinLevel.INFO,
                None,
                url="https://hooks.example.com",
            )

    async def test_an_address_waits_for_its_code(self, db, email_on, issue):
        channel = await create_channel(
            USER,
            NotificationChannelType.EMAIL,
            "Mail",
            NotificationChannelMinLevel.INFO,
            None,
            address="a@example.com",
        )

        assert channel.confirmed_at is None
        issue.assert_awaited_once_with(channel.id, USER.id, "a@example.com")

    async def test_an_address_whose_code_cannot_go_out_is_not_kept(
        self, db, email_on, issue
    ):
        issue.side_effect = EmailError("refused")

        with pytest.raises(EmailError):
            await create_channel(
                USER,
                NotificationChannelType.EMAIL,
                "Mail",
                NotificationChannelMinLevel.INFO,
                None,
                address="a@example.com",
            )

        db.delete_channel.assert_called_once()

    async def test_no_address_without_a_mail_server(self, db, mocker):
        mocker.patch.object(channels, "EMAIL_ENABLED", False)

        with pytest.raises(ChannelError, match="isn't set up"):
            await create_channel(
                USER,
                NotificationChannelType.EMAIL,
                "Mail",
                NotificationChannelMinLevel.INFO,
                None,
                address="a@example.com",
            )


class TestUpdate:
    async def test_keeps_the_secret_unless_given(self, db):
        stored = _stored(url="https://hooks.example.com/a", secret="k")

        updated = await update_channel(
            stored, USER, {}, url="https://hooks.example.com/b"
        )

        assert read_config(updated.config) == {
            "url": "https://hooks.example.com/b",
            "secret": "k",
        }

    @pytest.mark.parametrize(
        "url", ["https://elsewhere.example.com/a", "https://hooks.example.com:8443/a"]
    )
    async def test_a_kept_secret_does_not_follow_it_elsewhere(self, db, url):
        stored = _stored(url="https://hooks.example.com/a", secret="k")

        with pytest.raises(ChannelError, match="secret again"):
            await update_channel(stored, USER, {}, url=url)

        db.update_channel.assert_not_called()

    async def test_a_secret_given_again_goes_to_the_new_url(self, db):
        stored = _stored(url="https://hooks.example.com/a", secret="k")

        updated = await update_channel(
            stored,
            USER,
            {},
            url="https://elsewhere.example.com/a",
            secret="k2",
            secret_given=True,
        )

        assert read_config(updated.config)["secret"] == "k2"

    async def test_an_empty_secret_drops_it(self, db):
        stored = _stored(url="https://hooks.example.com/a", secret="k")

        updated = await update_channel(stored, USER, {}, secret="", secret_given=True)

        assert read_config(updated.config)["secret"] is None

    async def test_apprise_fields_left_out_stay(self, db):
        stored = _stored(
            NotificationChannelType.APPRISE, service="discord", fields=DISCORD
        )

        await update_channel(stored, ADMIN, {"name": "Phone"})

        db.update_channel.assert_called_once_with(4, ADMIN.id, {"name": "Phone"})

    async def test_an_apprise_secret_left_blank_stays(self, db):
        stored = _stored(
            NotificationChannelType.APPRISE, service="discord", fields=DISCORD
        )

        updated = await update_channel(
            stored, ADMIN, {}, fields={"webhook_id": "987654321", "botname": "RomM"}
        )

        assert read_config(updated.config)["fields"] == {
            "webhook_id": "987654321",
            "webhook_token": DISCORD["webhook_token"],
            "botname": "RomM",
        }

    async def test_new_apprise_fields_are_checked(self, db):
        stored = _stored(
            NotificationChannelType.APPRISE, service="ntfy", fields={"targets": ["a"]}
        )

        with pytest.raises(ChannelError, match="ntfy needs Targets"):
            await update_channel(stored, ADMIN, {}, fields={"targets": []})

        db.update_channel.assert_not_called()

    async def test_a_kept_apprise_secret_does_not_follow_a_new_host(self, db):
        stored = _stored(
            NotificationChannelType.APPRISE,
            service="ntfy",
            fields={"host": "ntfy.example.com", "targets": ["a"], "token": "tk_1"},
        )

        with pytest.raises(ChannelError, match="Enter Token again"):
            await update_channel(
                stored, ADMIN, {}, fields={"host": "evil.example.com", "targets": ["a"]}
            )

        db.update_channel.assert_not_called()

    async def test_a_demoted_admin_can_rename_but_not_repoint_it(self, db):
        stored = _stored(
            NotificationChannelType.APPRISE, service="discord", fields=DISCORD
        )

        await update_channel(stored, USER, {"name": "Old phone"})
        with pytest.raises(ChannelError, match="Only admins"):
            await update_channel(stored, USER, {}, fields=DISCORD)

    async def test_turning_it_back_on_forgets_past_failures(self, db):
        stored = _stored(url="https://hooks.example.com/a")
        stored.enabled = False

        updated = await update_channel(stored, USER, {"enabled": True})

        assert updated.consecutive_failures == 0

    async def test_a_new_address_is_confirmed_again(self, db, email_on, issue):
        stored = _stored(NotificationChannelType.EMAIL, address="a@example.com")

        updated = await update_channel(stored, USER, {}, address="b@example.com")

        assert updated.confirmed_at is None
        issue.assert_awaited_once_with(4, USER.id, "b@example.com")

    async def test_a_new_address_whose_code_cannot_go_out_is_not_kept(
        self, db, email_on, issue
    ):
        issue.side_effect = CodeCooldownError("Wait a minute")
        stored = _stored(NotificationChannelType.EMAIL, address="a@example.com")

        with pytest.raises(CodeCooldownError):
            await update_channel(
                stored, USER, {"name": "Mail"}, address="b@example.com"
            )

        db.update_channel.assert_not_called()

    async def test_the_same_address_changes_nothing(self, db, email_on, issue):
        stored = _stored(NotificationChannelType.EMAIL, address="a@example.com")

        await update_channel(stored, USER, {}, address="a@example.com")

        db.update_channel.assert_not_called()
        issue.assert_not_awaited()


class TestSendSample:
    async def test_reports_the_failure_without_counting_it(self, db, mocker):
        mocker.patch.object(
            channels, "send_to_channel", AsyncMock(side_effect=EmailError("refused"))
        )

        error = await send_sample(_stored(url="https://h.example.com"), USER)

        assert error == "refused"
        db.record_failure.assert_called_once_with(4, "refused", counts=False)

    async def test_an_unconfirmed_address_cannot_be_tried(self, db):
        with pytest.raises(ChannelError):
            await send_sample(
                _stored(NotificationChannelType.EMAIL, confirmed=False), USER
            )


class TestConfirm:
    async def test_the_right_code_confirms(self, db, mocker):
        mocker.patch.object(channels, "check_code", AsyncMock(return_value=True))

        confirmed = await confirm_channel(
            _stored(NotificationChannelType.EMAIL, confirmed=False), USER, "123456"
        )

        assert confirmed.confirmed_at is not None

    async def test_a_wrong_code_is_refused(self, db, mocker):
        mocker.patch.object(channels, "check_code", AsyncMock(return_value=False))

        with pytest.raises(ChannelError, match="wrong"):
            await confirm_channel(
                _stored(NotificationChannelType.EMAIL, confirmed=False), USER, "1"
            )


class TestResend:
    async def test_sends_to_the_stored_address(self, db, email_on, issue):
        await resend_code(
            _stored(
                NotificationChannelType.EMAIL, confirmed=False, address="a@example.com"
            )
        )

        issue.assert_awaited_once_with(4, USER.id, "a@example.com")

    async def test_a_webhook_needs_no_code(self, db, email_on, issue):
        with pytest.raises(ChannelError):
            await resend_code(_stored(url="https://h.example.com"))
