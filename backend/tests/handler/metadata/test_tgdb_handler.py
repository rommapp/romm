import pytest

from handler.metadata import tgdb_handler
from handler.metadata.tgdb_handler import TGDB_PLATFORM_LIST, TGDBHandler
from utils.platform_slugs import UniversalPlatformSlug as UPS


@pytest.mark.parametrize("enabled", [True, False])
async def test_the_heartbeat_follows_the_setting(
    monkeypatch: pytest.MonkeyPatch, enabled: bool
):
    monkeypatch.setattr(tgdb_handler, "TGDB_API_ENABLED", enabled)

    assert TGDBHandler.is_enabled() is enabled
    assert await TGDBHandler().heartbeat() is enabled


def test_a_known_platform_carries_its_tgdb_details():
    entry = TGDB_PLATFORM_LIST[UPS._3DO]

    assert TGDBHandler().get_platform("3do") == {
        "tgdb_id": 25,
        "slug": "3do",
        "name": "3DO",
        "family_name": "Panasonic",
        "url_logo": entry["url_logo"],
    }


def test_an_unknown_platform_has_no_tgdb_id():
    assert TGDBHandler().get_platform("not-a-platform") == {
        "tgdb_id": None,
        "slug": "not-a-platform",
    }
