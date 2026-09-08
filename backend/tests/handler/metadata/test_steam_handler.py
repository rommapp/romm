from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.services.steam_types import SteamAppDetails
from handler.metadata.steam_handler import (
    SteamHandler,
    _parse_release_date,
    extract_steam_metadata,
)

CYBERPUNK: SteamAppDetails = {
    "type": "game",
    "name": "Cyberpunk 2077",
    "steam_appid": 1091500,
    "required_age": "18",
    "is_free": False,
    "short_description": "An open-world, action-adventure RPG.",
    "header_image": "https://cdn.example/header.jpg",
    "website": "https://www.cyberpunk.net",
    "developers": ["CD PROJEKT RED"],
    "publishers": ["CD PROJEKT RED"],
    "platforms": {"windows": True, "mac": True, "linux": False},
    "metacritic": {"score": 86, "url": "https://www.metacritic.com/game/cyberpunk"},
    "categories": [
        {"id": 2, "description": "Single-player"},
        {"id": 22, "description": "Steam Achievements"},
    ],
    "genres": [{"id": "3", "description": "RPG"}],
    "screenshots": [
        {
            "id": 0,
            "path_thumbnail": "https://cdn.example/t0.jpg",
            "path_full": "https://cdn.example/f0.jpg",
        },
    ],
    "release_date": {"coming_soon": False, "date": "10 Dec, 2020"},
    "controller_support": "full",
}


def _handler(search_result=None, details=None) -> tuple[SteamHandler, MagicMock]:
    handler = SteamHandler()
    service = MagicMock()
    service.search_apps = AsyncMock(return_value=search_result or [])
    service.get_app_details = AsyncMock(return_value=details)
    service.get_library_capsule_url = AsyncMock(
        return_value="https://cdn.example/library_600x900.jpg"
    )
    handler.steam_service = service
    return handler, service


@pytest.fixture(autouse=True)
def steam_enabled():
    """Enabled is the default; the disabled-path tests override it."""
    with patch("handler.metadata.steam_handler.STEAM_API_ENABLED", True):
        yield


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10 Dec, 2020", 1607558400),
        ("Dec 10, 2020", 1607558400),
        ("2020", None),
        ("Q1 2021", None),
        ("", None),
    ],
)
def test_parse_release_date(raw, expected):
    assert _parse_release_date(raw) == expected


def test_extract_metadata_shapes_shared_keys():
    metadata = extract_steam_metadata(CYBERPUNK)

    # Keys shared with the other providers keep their names and shapes.
    assert metadata["genres"] == ["RPG"]
    assert metadata["companies"] == ["CD PROJEKT RED"]
    assert metadata["game_modes"] == ["Single player"]
    assert metadata["total_rating"] == "86"
    assert metadata["first_release_date"] == 1607558400
    # Steam-specific extras.
    assert metadata["developers"] == ["CD PROJEKT RED"]
    assert metadata["publishers"] == ["CD PROJEKT RED"]
    assert metadata["platforms"] == {"windows": True, "mac": True, "linux": False}
    assert metadata["required_age"] == 18
    assert metadata["is_free"] is False


def test_extract_metadata_skips_unreleased_dates():
    details = cast(
        SteamAppDetails,
        {**CYBERPUNK, "release_date": {"coming_soon": True, "date": "Q1 2027"}},
    )
    assert "first_release_date" not in extract_steam_metadata(details)


def test_extract_metadata_dedupes_companies():
    details = cast(
        SteamAppDetails,
        {**CYBERPUNK, "developers": ["Valve"], "publishers": ["Valve", "Sierra"]},
    )
    assert extract_steam_metadata(details)["companies"] == ["Valve", "Sierra"]


@patch("handler.metadata.steam_handler.STEAM_API_ENABLED", False)
async def test_get_rom_returns_empty_when_disabled():
    handler, service = _handler()
    rom = await handler.get_rom("Cyberpunk 2077.zip", "win")

    assert rom == {"steam_id": None}
    service.search_apps.assert_not_awaited()


async def test_get_rom_skips_non_pc_platforms():
    """A retro platform can have no Steam counterpart, so spend no requests."""
    handler, service = _handler()
    rom = await handler.get_rom("Super Mario World.sfc", "snes")

    assert rom == {"steam_id": None}
    service.search_apps.assert_not_awaited()
    service.get_app_details.assert_not_awaited()


async def test_get_rom_matches_by_name():
    handler, service = _handler(
        search_result=[
            {"type": "app", "name": "Cyberpunk 2077", "id": 1091500},
            {"type": "dlc", "name": "Cyberpunk 2077: Phantom Liberty", "id": 2138330},
        ],
        details=CYBERPUNK,
    )

    rom = await handler.get_rom("Cyberpunk 2077 (2020).zip", "win")

    assert rom["steam_id"] == 1091500
    assert rom["name"] == "Cyberpunk 2077"
    assert rom["summary"] == "An open-world, action-adventure RPG."
    assert rom["url_screenshots"] == ["https://cdn.example/f0.jpg"]
    assert rom["steam_metadata"]["genres"] == ["RPG"]
    service.get_app_details.assert_awaited_once_with(1091500)


async def test_get_rom_ignores_non_app_search_hits():
    """Soundtracks and DLC share the search index with games."""
    handler, service = _handler(
        search_result=[
            {"type": "dlc", "name": "Cyberpunk 2077", "id": 2138330},
        ]
    )

    rom = await handler.get_rom("Cyberpunk 2077.zip", "win")

    assert rom == {"steam_id": None}
    service.get_app_details.assert_not_awaited()


async def test_get_rom_rejects_apps_that_are_not_games():
    """The search hit's coarse type does not distinguish a demo or a video."""
    handler, service = _handler(
        search_result=[{"type": "app", "name": "Cyberpunk 2077", "id": 1091500}],
        details=cast(SteamAppDetails, {**CYBERPUNK, "type": "demo"}),
    )

    rom = await handler.get_rom("Cyberpunk 2077.zip", "win")

    assert rom == {"steam_id": None}


async def test_get_rom_rejects_weak_name_matches():
    handler, service = _handler(
        search_result=[{"type": "app", "name": "Totally Unrelated Game", "id": 42}]
    )

    rom = await handler.get_rom("Cyberpunk 2077.zip", "win")

    assert rom == {"steam_id": None}
    service.get_app_details.assert_not_awaited()


async def test_get_rom_honours_filename_tag():
    """A pinned id skips search entirely, which is the point of the tag."""
    handler, service = _handler(details=CYBERPUNK)

    rom = await handler.get_rom("Some Ambiguous Name (steam-1091500).zip", "win")

    assert rom["steam_id"] == 1091500
    service.search_apps.assert_not_awaited()
    service.get_app_details.assert_awaited_once_with(1091500)


async def test_get_rom_by_id_missing_app():
    handler, service = _handler(details=None)

    assert await handler.get_rom_by_id(999999999) == {"steam_id": None}


async def test_cover_falls_back_to_the_header_image():
    handler, service = _handler(details=CYBERPUNK)
    service.get_library_capsule_url = AsyncMock(return_value=None)

    rom = await handler.get_rom_by_id(1091500)

    assert rom["url_cover"] == "https://cdn.example/header.jpg"


async def test_heartbeat_reports_reachability():
    handler, service = _handler(details=CYBERPUNK)
    assert await handler.heartbeat() is True
    # Reachability only, so don't pull the whole store page.
    await_args = service.get_app_details.await_args
    assert await_args is not None
    assert await_args.kwargs["filters"] == "basic"

    assert await _handler(details=None)[0].heartbeat() is False


@patch("handler.metadata.steam_handler.STEAM_API_ENABLED", False)
async def test_heartbeat_false_when_disabled():
    assert await _handler(details=CYBERPUNK)[0].heartbeat() is False
