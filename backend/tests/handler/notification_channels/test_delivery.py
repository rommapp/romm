from unittest.mock import MagicMock

import pytest

from handler.notification_channels import delivery
from handler.notification_channels.delivery import (
    deliver_to_channel,
    enqueue_channel_deliveries,
    forwards,
)
from handler.notification_channels.webhook import WebhookError
from models.notification import NotificationKind, NotificationLevel, NotificationTopic
from models.user import Role

from .fixtures import make_notification


def _channel(**overrides) -> MagicMock:
    fields = {
        "id": 3,
        "user_id": 5,
        "name": "Discord",
        "enabled": True,
        "min_level": NotificationLevel.INFO,
        "topics": None,
    }
    return MagicMock(**{**fields, **overrides})


class TestForwards:
    @pytest.mark.parametrize(
        "min_level,level,expected",
        [
            (NotificationLevel.INFO, NotificationLevel.SUCCESS, True),
            (NotificationLevel.WARNING, NotificationLevel.SUCCESS, False),
            (NotificationLevel.WARNING, NotificationLevel.ERROR, True),
            (NotificationLevel.ERROR, NotificationLevel.WARNING, False),
        ],
    )
    def test_by_level(self, min_level, level, expected):
        assert (
            forwards(_channel(min_level=min_level), make_notification(level=level))
            is expected
        )

    @pytest.mark.parametrize(
        "kind,expected",
        [
            (NotificationKind.SCAN_FAILED, True),
            (NotificationKind.TASK_FAILED, False),
            ("argosy.sync_done", True),
        ],
    )
    def test_by_topic(self, kind, expected):
        channel = _channel(topics=[NotificationTopic.SCANS, NotificationTopic.CUSTOM])

        assert forwards(channel, make_notification(kind=kind)) is expected


class TestEnqueue:
    def test_queues_each_channel_that_wants_it(self, mocker):
        mocker.patch.object(
            delivery.db_notification_channel_handler,
            "get_deliverable_channels",
            return_value=[
                _channel(id=1, user_id=5),
                _channel(id=2, user_id=5, min_level=NotificationLevel.ERROR),
                _channel(id=3, user_id=6),
            ],
        )
        enqueue = mocker.patch.object(delivery.low_prio_queue, "enqueue")

        enqueue_channel_deliveries([(5, make_notification())])

        [call] = enqueue.call_args_list
        assert call.args == (deliver_to_channel,)
        assert call.kwargs["kwargs"]["channel_id"] == 1
        assert call.kwargs["kwargs"]["notification"]["id"] == 7
        assert call.kwargs["result_ttl"] == 0

    def test_never_raises_into_the_inbox(self, mocker):
        mocker.patch.object(
            delivery.db_notification_channel_handler,
            "get_deliverable_channels",
            side_effect=RuntimeError("database gone"),
        )

        enqueue_channel_deliveries([(5, make_notification())])


class TestDeliverToChannel:
    @pytest.fixture
    def db(self, mocker):
        handler = mocker.patch.object(delivery, "db_notification_channel_handler")
        handler.get_channel_for_delivery.return_value = (_channel(), Role.USER)
        handler.turn_off_if_failing.return_value = False
        return handler

    @pytest.fixture
    def send(self, mocker):
        return mocker.patch.object(delivery, "send_to_channel")

    def _run(self):
        deliver_to_channel(3, make_notification().model_dump(mode="json"))

    def test_records_a_delivery(self, db, send):
        self._run()

        assert send.await_args.kwargs == {"allow_private": False}
        db.record_delivery.assert_called_once_with(3)

    def test_an_admins_channel_may_reach_the_local_network(self, db, send):
        db.get_channel_for_delivery.return_value = (_channel(), Role.ADMIN)

        self._run()

        assert send.await_args.kwargs == {"allow_private": True}

    def test_skips_a_channel_turned_off_meanwhile(self, db, send):
        db.get_channel_for_delivery.return_value = (_channel(enabled=False), Role.ADMIN)

        self._run()

        send.assert_not_called()

    def test_a_failure_with_retries_left_is_raised_for_rq(self, mocker, db, send):
        send.side_effect = WebhookError("discord.com answered 502")
        mocker.patch.object(
            delivery, "get_current_job", return_value=MagicMock(retries_left=2)
        )

        with pytest.raises(WebhookError):
            self._run()

        db.record_failure.assert_called_once_with(
            3, "discord.com answered 502", counts=False
        )

    def test_the_last_failure_counts_and_can_turn_the_channel_off(
        self, mocker, db, send
    ):
        send.side_effect = WebhookError("discord.com answered 404")
        mocker.patch.object(
            delivery, "get_current_job", return_value=MagicMock(retries_left=0)
        )
        db.turn_off_if_failing.return_value = True
        tell = mocker.patch.object(delivery, "_tell_owner_channel_is_off")

        self._run()

        db.record_failure.assert_called_once_with(
            3, "discord.com answered 404", counts=True
        )
        channel, error = tell.await_args.args
        assert (channel.id, error) == (3, "discord.com answered 404")
