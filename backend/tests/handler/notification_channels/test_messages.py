import pytest

from handler.notification_channels import messages
from handler.notification_channels.messages import render
from models.notification import NotificationKind

from .fixtures import make_notification


@pytest.fixture(autouse=True)
def base_url(mocker):
    return mocker.patch.object(
        messages, "get_public_base_url", return_value="https://romm.example.com"
    )


@pytest.mark.parametrize(
    "kind,data,title,body,url",
    [
        (
            NotificationKind.SCAN_COMPLETED,
            {"new_roms": 3},
            "Scan completed",
            "3 new games",
            "https://romm.example.com/scan",
        ),
        (
            NotificationKind.SCAN_COMPLETED,
            {"new_roms": 1},
            "Scan completed",
            "1 new game",
            "https://romm.example.com/scan",
        ),
        (
            NotificationKind.SCAN_COMPLETED,
            {"new_roms": 0},
            "Scan completed",
            "No new games",
            "https://romm.example.com/scan",
        ),
        (
            NotificationKind.SCAN_FAILED,
            {"error": "Disk gone"},
            "Scan failed",
            "Disk gone",
            "https://romm.example.com/scan",
        ),
        (
            NotificationKind.TASK_FAILED,
            {"title": "Cleanup", "error": "Timed out"},
            "Cleanup failed",
            "Timed out",
            "https://romm.example.com/administration",
        ),
        (
            NotificationKind.TASK_COMPLETED,
            {"title": "Cleanup"},
            "Cleanup finished",
            None,
            "https://romm.example.com/administration",
        ),
        (
            NotificationKind.STREAMING_SESSION_ENDED,
            {"rom_name": "Zelda", "rom_id": 12, "reason": "Maintenance"},
            "Your stream of Zelda was ended",
            "Maintenance",
            "https://romm.example.com/rom/12",
        ),
        (
            NotificationKind.STREAMING_SESSION_ENDED,
            {},
            "Your streaming session was ended",
            None,
            None,
        ),
        (
            NotificationKind.ROLE_CHANGED,
            {"role": "admin"},
            "Your role is now Admin",
            None,
            None,
        ),
        (
            NotificationKind.CHANNEL_DISABLED,
            {"name": "Discord", "error": "discord.com answered 404"},
            "Discord was turned off",
            "discord.com answered 404",
            "https://romm.example.com/notifications?tab=channels",
        ),
    ],
)
def test_words_romms_own_kinds_in_english(kind, data, title, body, url):
    message = render(make_notification(kind=kind, data=data, title=None, body=None))

    assert (message.title, message.body, message.url) == (title, body, url)


def test_a_custom_kind_carries_its_own_text():
    message = render(make_notification(kind="argosy.sync_done"))

    assert message.title == "Maintenance tonight"
    assert message.body == "RomM restarts at 23:00"
    assert message.url == "https://romm.example.com/platforms"


def test_links_nowhere_without_a_shareable_base_url(base_url):
    base_url.return_value = None

    assert render(make_notification()).url is None


def test_ignores_data_of_the_wrong_type():
    message = render(
        make_notification(kind=NotificationKind.SCAN_COMPLETED, data={"new_roms": True})
    )

    assert message.body == "No new games"
