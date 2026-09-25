import logging
from typing import Any

import pytest
from apprise import Apprise, NotifyFormat, NotifyType

from handler.notification_channels import apprise_channel
from handler.notification_channels.apprise_channel import (
    AppriseError,
    FieldValue,
    build_url,
    checked_fields,
    describe,
    find_service,
    merge_fields,
    send,
    services,
    split_fields,
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
        # Local schemas, and FCM whose key file Apprise opens itself.
        assert not {"syslog", "fcm"} & set(ids)
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

    @pytest.mark.parametrize(
        "service,key", [("mastodon", "token"), ("rocket", "webhook"), ("json", "path")]
    )
    def test_treats_credentials_as_secrets_even_unflagged(self, service, key):
        field = find_service(service).field(key)

        assert field is not None
        assert field.private


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
        assert build_url(find_service(service), fields) == url
        checked_fields(service, fields)

    def test_says_what_is_missing(self):
        with pytest.raises(ValueError, match="^Discord needs Webhook Token$"):
            build_url(find_service("discord"), {"webhook_id": "1234567890"})

    def test_refuses_fields_no_template_takes_together(self):
        fields: dict[str, FieldValue] = {
            "host": "h.example.com",
            "targets": ["a"],
            "user": "u",
            "token": "t",
        }

        with pytest.raises(ValueError, match="can't take these fields together"):
            build_url(find_service("ntfy"), {**fields, "password": "p"})

    @pytest.mark.parametrize(
        "host", ["example.com/hook?x=1", "{port}.example.com", "example.com:8080"]
    )
    def test_a_host_is_only_a_host(self, host):
        with pytest.raises(ValueError, match="isn't a hostname"):
            build_url(find_service("json"), {"host": host, "port": 80})

    @pytest.mark.parametrize("host", ["ntfy.example.com", "192.168.1.5", "[::1]"])
    def test_takes_names_and_addresses_as_hosts(self, host):
        assert build_url(
            find_service("ntfy"), {"host": host, "targets": ["romm"]}
        ).startswith(f"ntfys://{host}/")

    def test_ignores_fields_the_form_never_offered(self):
        url = build_url(
            find_service("discord"), {**_DISCORD, "template": "/etc/passwd"}
        )

        assert "template" not in url

    @pytest.mark.parametrize("service", ["syslog", "fcm", "nowhere"])
    def test_knows_only_the_services_it_lists(self, service):
        with pytest.raises(ValueError, match="no such service"):
            find_service(service)


class TestFields:
    def test_describes_the_service_and_hides_its_token(self):
        assert describe("discord", _DISCORD) == ("Discord", "discord://1...0/a...p/")

    def test_describes_fields_it_can_no_longer_use_as_nothing(self):
        assert describe("discord", {}) == (None, "")

    def test_hides_secrets_apprise_would_show(self):
        _, target = describe("json", {"host": "hooks.example.com", "path": "t0ken"})

        assert target == "jsons://hooks.example.com/****"

    def test_hands_the_form_what_isnt_secret_and_names_the_secrets(self):
        assert split_fields("discord", {**_DISCORD, "botname": "RomM"}) == (
            {"botname": "RomM"},
            ["webhook_id", "webhook_token"],
        )

    def test_check_keeps_only_the_fields_the_service_takes(self):
        assert (
            checked_fields("discord", {**_DISCORD, "junk": "x", "botname": ""})
            == _DISCORD
        )

    def test_a_refusal_hides_the_secret_it_quotes(self):
        with pytest.raises(ValueError, match=r"Token \(\*\*\*\*\)"):
            checked_fields("slack", {"access_token": "nope-abc"})


class TestMergeFields:
    _NTFY: dict[str, FieldValue] = {
        "host": "ntfy.example.com",
        "targets": ["romm"],
        "token": "tk_1",
    }

    def test_a_secret_left_out_stays(self):
        merged = merge_fields("discord", _DISCORD, {"webhook_id": "1234567890"})

        assert merged == _DISCORD

    def test_an_empty_secret_goes(self):
        given: dict[str, FieldValue] = {
            **self._NTFY,
            "token": "",
            "user": "me",
            "password": "pw",
        }

        assert merge_fields("ntfy", self._NTFY, given) == {
            "host": "ntfy.example.com",
            "targets": ["romm"],
            "user": "me",
            "password": "pw",
        }

    @pytest.mark.parametrize(
        "change",
        [{"host": "elsewhere.example.com"}, {"port": 8443}, {"schema": "ntfy"}],
    )
    def test_a_kept_secret_does_not_follow_the_channel_elsewhere(self, change):
        given: dict[str, FieldValue] = {
            "host": "ntfy.example.com",
            "targets": ["romm"],
            **change,
        }

        with pytest.raises(ValueError, match="Enter Token again"):
            merge_fields("ntfy", self._NTFY, given)

    def test_a_secret_given_again_goes_to_the_new_address(self):
        given: dict[str, FieldValue] = {
            "host": "elsewhere.example.com",
            "targets": ["romm"],
            "token": "tk_2",
        }

        assert merge_fields("ntfy", self._NTFY, given) == given


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

    def test_mentions_ping_nobody(self, notify):
        calls = notify()

        send("json", _JSON, _message(title="@everyone look", body="<@123> and @here"))

        [(_, kwargs)] = calls
        assert kwargs["title"] == "@\u200beveryone look"
        assert kwargs["body"].startswith("<\u200b@123> and @\u200bhere")

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
