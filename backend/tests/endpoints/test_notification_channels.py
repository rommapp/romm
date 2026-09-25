import re
from unittest.mock import AsyncMock

import pytest
from fastapi import status

from handler.database import db_notification_channel_handler
from handler.email_handler import EmailError
from handler.notification_channels import channels, confirmation
from models.notification_channel import (
    MAX_CONSECUTIVE_DELIVERY_FAILURES,
    MAX_NOTIFICATION_CHANNELS_PER_USER,
)

API = "/api/notification-channels"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _webhook(url: str = "https://hooks.example.com/romm/token", **fields) -> dict:
    return {"type": "webhook", "name": "Hook", "url": url, **fields}


_DISCORD = {"webhook_id": "1234567890", "webhook_token": "abcdefghijklmnop"}


def _apprise(service: str = "discord", **fields) -> dict:
    return {
        "type": "apprise",
        "name": "Discord",
        "service": service,
        "fields": fields or _DISCORD,
    }


@pytest.fixture
def emailed(mocker):
    mocker.patch.object(channels, "EMAIL_ENABLED", True)
    return mocker.patch.object(confirmation, "send_email")


@pytest.fixture
def sent(mocker):
    return mocker.patch.object(channels, "send_to_channel", AsyncMock())


class TestCreate:
    def test_a_webhook_hides_its_token(self, client, access_token):
        response = client.post(
            API, json=_webhook(secret="k"), headers=_auth(access_token)
        )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["target"] == "https://hooks.example.com/…oken"
        assert body["has_secret"] is True
        assert body["confirmed"] is True
        assert body["topics"] is None
        assert "token" not in response.text

    def test_an_admin_may_reach_the_local_network(self, client, access_token):
        response = client.post(
            API, json=_webhook("http://192.168.1.2/hook"), headers=_auth(access_token)
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_a_user_may_not(self, client, viewer_access_token):
        response = client.post(
            API,
            json=_webhook("http://192.168.1.2/hook"),
            headers=_auth(viewer_access_token),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_admin_forwards_through_apprise(self, client, access_token):
        response = client.post(
            API, json=_apprise(**_DISCORD, botname="RomM"), headers=_auth(access_token)
        )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert (body["type"], body["service"], body["service_name"]) == (
            "apprise",
            "discord",
            "Discord",
        )
        assert body["target"] == "discord://RomM@1...0/a...p/"
        assert body["fields"] == {"botname": "RomM"}
        assert body["stored_secrets"] == ["webhook_id", "webhook_token"]
        assert "abcdefghijklmnop" not in response.text

    def test_a_user_may_not_use_apprise(self, client, viewer_access_token):
        response = client.post(API, json=_apprise(), headers=_auth(viewer_access_token))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Only admins can use Apprise channels"

    @pytest.mark.parametrize(
        "payload",
        [_apprise("syslog", host="localhost"), _apprise(webhook_id="1234567890")],
    )
    def test_fields_apprise_cannot_use_are_refused(self, client, access_token, payload):
        response = client.post(API, json=payload, headers=_auth(access_token))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_user_has_at_most_so_many(self, client, access_token):
        for n in range(MAX_NOTIFICATION_CHANNELS_PER_USER):
            created = client.post(
                API, json=_webhook(name=f"Hook {n}"), headers=_auth(access_token)
            )
            assert created.status_code == status.HTTP_201_CREATED

        response = client.post(
            API, json=_webhook(name="One more"), headers=_auth(access_token)
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "at most" in response.json()["detail"]

    @pytest.mark.parametrize(
        "payload",
        [
            {"type": "sms", "name": "x", "url": "https://example.com"},
            {"type": "email", "name": "x", "address": "not-an-address"},
            {"type": "apprise", "name": "x", "service": "discord"},
            _webhook(topics=["everything"]),
            _webhook(name=""),
        ],
    )
    def test_refuses_a_malformed_channel(self, client, access_token, payload):
        response = client.post(API, json=payload, headers=_auth(access_token))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_no_email_without_a_mail_server(self, client, access_token, mocker):
        mocker.patch.object(channels, "EMAIL_ENABLED", False)

        response = client.post(
            API,
            json={"type": "email", "name": "Mail", "address": "a@example.com"},
            headers=_auth(access_token),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_address_the_server_refuses_is_not_kept(
        self, client, access_token, admin_user, emailed
    ):
        emailed.side_effect = EmailError("The SMTP server refused the message")

        response = client.post(
            API,
            json={"type": "email", "name": "Mail", "address": "a@example.com"},
            headers=_auth(access_token),
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert db_notification_channel_handler.get_channels(admin_user.id) == []


class TestAppriseServices:
    def test_an_admin_gets_each_service_with_its_fields(self, client, access_token):
        response = client.get(f"{API}/apprise-services", headers=_auth(access_token))

        assert response.status_code == status.HTTP_200_OK
        discord = next(s for s in response.json() if s["id"] == "discord")
        token = next(f for f in discord["fields"] if f["key"] == "webhook_token")
        assert discord["name"] == "Discord"
        assert (token["required"], token["private"], token["advanced"]) == (
            True,
            True,
            False,
        )

    def test_a_user_gets_none(self, client, viewer_access_token):
        response = client.get(
            f"{API}/apprise-services", headers=_auth(viewer_access_token)
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestEmailConfirmation:
    def test_the_emailed_code_confirms_the_address(self, client, access_token, emailed):
        created = client.post(
            API,
            json={"type": "email", "name": "Mail", "address": "a@example.com"},
            headers=_auth(access_token),
        ).json()
        match = re.search(r"Your code is (\d{6})", emailed.call_args.args[2])
        assert match is not None
        code = match.group(1)
        wrong = "000000" if code != "000000" else "111111"

        assert created["confirmed"] is False
        assert created["target"] == "a@example.com"
        refused = client.post(
            f"{API}/{created['id']}/confirm",
            json={"code": wrong},
            headers=_auth(access_token),
        )
        assert refused.status_code == status.HTTP_400_BAD_REQUEST

        confirmed = client.post(
            f"{API}/{created['id']}/confirm",
            json={"code": code},
            headers=_auth(access_token),
        )
        assert confirmed.status_code == status.HTTP_200_OK
        assert confirmed.json()["confirmed"] is True

    def test_a_new_code_has_to_wait(self, client, access_token, emailed):
        created = client.post(
            API,
            json={"type": "email", "name": "Mail", "address": "a@example.com"},
            headers=_auth(access_token),
        ).json()

        response = client.post(
            f"{API}/{created['id']}/resend-code", headers=_auth(access_token)
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestOwnership:
    def test_each_user_sees_only_their_own(
        self, client, access_token, viewer_access_token
    ):
        client.post(API, json=_webhook(), headers=_auth(access_token))

        response = client.get(API, headers=_auth(viewer_access_token))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.parametrize(
        "method,suffix",
        [("patch", ""), ("delete", ""), ("post", "/test"), ("post", "/resend-code")],
    )
    def test_someone_elses_is_not_found(
        self, client, access_token, viewer_access_token, method, suffix
    ):
        created = client.post(API, json=_webhook(), headers=_auth(access_token)).json()

        response = client.request(
            method,
            f"{API}/{created['id']}{suffix}",
            json={} if method == "patch" else None,
            headers=_auth(viewer_access_token),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdate:
    def test_changes_the_filters_and_drops_the_secret(self, client, access_token):
        created = client.post(
            API, json=_webhook(secret="k"), headers=_auth(access_token)
        ).json()

        response = client.patch(
            f"{API}/{created['id']}",
            json={
                "min_level": "warning",
                "topics": ["scans", "tasks"],
                "secret": "",
                "enabled": False,
            },
            headers=_auth(access_token),
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["min_level"] == "warning"
        assert body["topics"] == ["scans", "tasks"]
        assert body["has_secret"] is False
        assert body["enabled"] is False

    def test_apprise_secrets_stay_until_given_again(self, client, access_token):
        created = client.post(API, json=_apprise(), headers=_auth(access_token)).json()
        path = f"{API}/{created['id']}"

        renamed = client.patch(
            path, json={"name": "Phone"}, headers=_auth(access_token)
        )
        retitled = client.patch(
            path,
            json={"fields": {"webhook_id": "1234567890", "botname": "Bot"}},
            headers=_auth(access_token),
        )

        assert renamed.json()["target"] == created["target"]
        assert retitled.json()["target"] == "discord://Bot@1...0/a...p/"

    def test_null_topics_forwards_everything_again(self, client, access_token):
        created = client.post(
            API, json=_webhook(topics=["scans"]), headers=_auth(access_token)
        ).json()

        response = client.patch(
            f"{API}/{created['id']}", json={"topics": None}, headers=_auth(access_token)
        )

        assert response.json()["topics"] is None


class TestTest:
    def test_a_delivery_is_recorded(self, client, access_token, sent):
        created = client.post(API, json=_webhook(), headers=_auth(access_token)).json()

        response = client.post(
            f"{API}/{created['id']}/test", headers=_auth(access_token)
        )

        assert response.json() == {"ok": True, "error": None}
        [listed] = client.get(API, headers=_auth(access_token)).json()
        assert listed["last_delivered_at"] is not None

    def test_a_failure_is_reported_but_not_counted(self, client, access_token, sent):
        sent.side_effect = EmailError("refused")
        created = client.post(API, json=_webhook(), headers=_auth(access_token)).json()

        response = client.post(
            f"{API}/{created['id']}/test", headers=_auth(access_token)
        )

        assert response.json() == {"ok": False, "error": "refused"}
        [listed] = client.get(API, headers=_auth(access_token)).json()
        assert listed["last_error"] == "refused"
        assert listed["consecutive_failures"] == 0


class TestDeliveryBookkeeping:
    def test_turns_off_once_it_failed_too_often(self, client, access_token, admin_user):
        created = client.post(API, json=_webhook(), headers=_auth(access_token)).json()

        for _ in range(MAX_CONSECUTIVE_DELIVERY_FAILURES - 1):
            db_notification_channel_handler.record_failure(
                created["id"], "boom", counts=True
            )
        assert not db_notification_channel_handler.turn_off_if_failing(created["id"])

        db_notification_channel_handler.record_failure(
            created["id"], "boom", counts=True
        )
        assert db_notification_channel_handler.turn_off_if_failing(created["id"])
        assert not db_notification_channel_handler.turn_off_if_failing(created["id"])
        assert (
            db_notification_channel_handler.get_deliverable_channels([admin_user.id])
            == []
        )

    def test_an_unconfirmed_address_gets_nothing(
        self, client, access_token, admin_user, emailed
    ):
        client.post(
            API,
            json={"type": "email", "name": "Mail", "address": "a@example.com"},
            headers=_auth(access_token),
        )

        assert (
            db_notification_channel_handler.get_deliverable_channels([admin_user.id])
            == []
        )
