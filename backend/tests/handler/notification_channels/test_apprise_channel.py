import logging
from typing import Any

import pytest
from apprise import Apprise, NotifyFormat, NotifyType

from handler.notification_channels import apprise_channel
from handler.notification_channels.apprise_channel import (
    AppriseError,
    FieldValue,
    build_url,
    check,
    describe,
    find_service,
    merge_fields,
    public_fields,
    send,
    services,
)
from handler.notification_channels.messages import OutboundMessage
from models.notification import NotificationLevel

from .fixtures import make_notification

_DISCORD = {"webhook_id": "1234567890", "webhook_token": "abcdefghijklmnop"}
_JSON = {"host": "hooks.example.com", "path": "romm"}


def _message(**overrides: Any) -> OutboundMessage:
    fields: dict[str, Any] = {
        "notification": make_notification(),
        "title": "Maintenance tonight",
        "body": "RomM restarts at 23:00",
        "url": "https://romm.example.com/platforms",
    }
    return OutboundMessage(**{**fields, **overrides})


def _keys(service_id: str, advanced: bool = False) -> list[str]:
    return [f.key for f in find_service(service_id).fields if f.advanced is advanced]


class TestCatalog:
    def test_lists_what_apprise_reaches_but_nothing_local(self):
        ids = [service.id for service in services()]

        assert {"discord", "ntfy", "tgram", "json"} <= set(ids)
        assert "syslog" not in ids
        names = [service.name.lower() for service in services()]
        assert names == sorted(names)

    def test_requires_only_what_every_template_needs(self):
        discord = find_service("discord")
        slack = find_service("slack")

        assert [f.key for f in discord.fields if f.required] == [
            "webhook_id",
            "webhook_token",
        ]
        # A bot token or three webhook tokens: neither is needed by both.
        assert not any(f.required for f in slack.fields)

    def test_a_list_stands_in_for_its_singular_tokens(self):
        targets = find_service("ntfy").field("targets")

        assert "topic" not in _keys("ntfy")
        assert targets is not None
        assert (targets.type, targets.required) == ("list", True)

    def test_offers_the_schema_only_when_there_is_a_choice(self):
        schema = find_service("ntfy").field("schema")

        assert schema is not None
        assert (schema.values, schema.default) == (("ntfy", "ntfys"), "ntfys")
        assert find_service("discord").field("schema") is None

    def test_leaves_out_options_romm_sets_or_that_read_files(self):
        options = _keys("discord", advanced=True)

        assert "ping" in options
        assert not {"template", "cto", "rto", "retry", "redirect", "url"} & set(options)

    def test_json_takes_a_path_after_its_host(self):
        assert "path" in _keys("json")


class TestBuildUrl:
    @pytest.mark.parametrize(
        "service,fields,url",
        [
            ("discord", _DISCORD, "discord://1234567890/abcdefghijklmnop"),
            (
                "discord",
                {**_DISCORD, "botname": "RomM", "image": True, "ping": ["@here"]},
                "discord://RomM@1234567890/abcdefghijklmnop?image=yes&ping=%40here",
            ),
            ("ntfy", {"targets": ["romm"]}, "ntfys://romm"),
            (
                "ntfy",
                {"host": "ntfy.example.com", "targets": ["romm"], "token": "tk_1"},
                "ntfys://tk_1@ntfy.example.com/romm",
            ),
            (
                "ntfy",
                {
                    "schema": "ntfy",
                    "host": "192.168.1.5",
                    "port": 8080,
                    "user": "me",
                    "password": "p@ss/word",
                    "targets": ["a", "b"],
                },
                "ntfy://me:p%40ss%2Fword@192.168.1.5:8080/a/b",
            ),
            (
                "gotify",
                {"host": "push.example.com", "path": "gotify", "token": "abc"},
                "gotifys://push.example.com/gotify/abc",
            ),
            (
                "json",
                {"host": "hooks.example.com", "path": "/api/romm"},
                "jsons://hooks.example.com/api/romm",
            ),
        ],
    )
    def test_fills_in_the_template_the_fields_make_up(self, service, fields, url):
        assert build_url(service, fields) == url
        check(service, fields)

    def test_says_what_is_missing(self):
        with pytest.raises(ValueError, match="^Discord needs Webhook Token$"):
            build_url("discord", {"webhook_id": "1234567890"})

    def test_refuses_fields_no_template_takes_together(self):
        fields: dict[str, FieldValue] = {
            "host": "h.example.com",
            "targets": ["a"],
            "user": "u",
            "token": "t",
        }

        with pytest.raises(ValueError, match="can't take these fields together"):
            build_url("ntfy", {**fields, "password": "p"})

    def test_a_host_is_only_a_host(self):
        with pytest.raises(ValueError, match="isn't a hostname"):
            build_url("json", {"host": "example.com/hook?x=1"})

    def test_ignores_fields_the_form_never_offered(self):
        url = build_url("discord", {**_DISCORD, "template": "/etc/passwd"})

        assert "template" not in url

    @pytest.mark.parametrize("service", ["syslog", "nowhere"])
    def test_knows_only_the_services_it_lists(self, service):
        with pytest.raises(ValueError, match="no such service"):
            build_url(service, {})


class TestFields:
    def test_describes_the_service_and_hides_its_token(self):
        assert describe("discord", _DISCORD) == ("Discord", "discord://1...0/a...p/")

    def test_describes_fields_it_can_no_longer_use_as_nothing(self):
        assert describe("discord", {}) == (None, "")

    def test_keeps_the_secrets_out_of_what_the_form_gets_back(self):
        assert public_fields("discord", {**_DISCORD, "botname": "RomM"}) == {
            "botname": "RomM"
        }

    def test_an_edit_keeps_the_secrets_it_leaves_blank(self):
        stored = {**_DISCORD, "botname": "RomM"}

        merged = merge_fields("discord", stored, {"webhook_token": "", "botname": ""})

        assert merged == _DISCORD


class TestSend:
    @pytest.fixture
    def notify(self, mocker):
        """Stands in for Apprise's notify; keeps what it got and returns `result`."""
        calls: list[tuple[Apprise, dict[str, Any]]] = []

        def install(result: bool = True, log: Any = None):
            def fake(self: Apprise, **kwargs: Any) -> bool:
                calls.append((self, kwargs))
                if log:
                    log()
                return result

            mocker.patch.object(apprise_channel.Apprise, "notify", fake)
            return calls

        return install

    def test_sends_the_title_body_and_link(self, notify):
        calls = notify()

        send("json", _JSON, _message())

        [(_, kwargs)] = calls
        assert kwargs == {
            "title": "Maintenance tonight",
            "body": "RomM restarts at 23:00\n\nhttps://romm.example.com/platforms",
            "notify_type": NotifyType.INFO,
            "body_format": NotifyFormat.TEXT,
        }

    def test_a_title_alone_is_also_the_body(self, notify):
        calls = notify()

        send("json", _JSON, _message(body=None, url=None))

        [(_, kwargs)] = calls
        assert kwargs["body"] == "Maintenance tonight"

    @pytest.mark.parametrize(
        "level,notify_type",
        [
            (NotificationLevel.INFO, NotifyType.INFO),
            (NotificationLevel.SUCCESS, NotifyType.SUCCESS),
            (NotificationLevel.WARNING, NotifyType.WARNING),
            (NotificationLevel.ERROR, NotifyType.FAILURE),
        ],
    )
    def test_carries_the_level(self, notify, level, notify_type):
        calls = notify()

        send("json", _JSON, _message(notification=make_notification(level=level)))

        [(_, kwargs)] = calls
        assert kwargs["notify_type"] == notify_type

    def test_holds_a_service_to_its_own_limits(self, notify):
        calls = notify()

        # Apprise gives email 15 seconds to connect.
        send("mailto", {"host": "smtp.example.com", "user": "me"}, _message())

        [(apprise, _)] = calls
        plugin = apprise[0]
        assert plugin.socket_connect_timeout == apprise_channel.CONNECT_TIMEOUT_SECONDS
        assert (plugin.retry, plugin.redirects) == (0, False)

    def test_a_refusal_says_what_apprise_warned_but_not_the_reply(self, notify):
        def log():
            logger = logging.getLogger("apprise")
            logger.warning("Failed to send JSON POST notification: error=500.")
            logger.debug("Response Details: internal secret")

        notify(result=False, log=log)

        with pytest.raises(AppriseError) as caught:
            send("json", _JSON, _message())

        assert str(caught.value) == "Failed to send JSON POST notification: error=500."

    def test_keeps_no_warning_logged_outside_a_send(self, notify):
        logging.getLogger("apprise").warning("Something from another send")
        notify(result=False)

        with pytest.raises(AppriseError, match="^JSON did not take the notification$"):
            send("json", _JSON, _message())

    def test_an_unreachable_service_is_an_apprise_error(self):
        with pytest.raises(AppriseError, match="Connection error"):
            send(
                "json",
                {"schema": "json", "host": "127.0.0.1", "port": 1},
                _message(),
            )
