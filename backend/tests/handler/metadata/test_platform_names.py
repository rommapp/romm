from collections.abc import Iterator
from unittest.mock import patch

import pytest

from adapters.services.igdb import IGDB_PLATFORM_LIST
from handler.metadata.platform_names import (
    platform_abbreviation,
    platform_alternative_names,
    resolve_platform_name,
)
from handler.metadata.ss_handler import SCREENSAVER_PLATFORM_LIST
from utils.platform_slugs import UniversalPlatformSlug as UPS


@pytest.fixture(autouse=True)
def clear_cache() -> Iterator[None]:
    platform_alternative_names.cache_clear()
    yield
    platform_alternative_names.cache_clear()


def test_resolves_the_first_providers_name() -> None:
    assert resolve_platform_name("genesis") == "Sega Mega Drive/Genesis"


def test_resolves_an_unknown_slug_to_its_title() -> None:
    assert resolve_platform_name("my-console") == "My Console"


def test_collects_other_providers_names_once() -> None:
    names = platform_alternative_names("genesis")

    assert {"Megadrive", "Genesis/Mega Drive", "Sega Genesis"} <= set(names)
    # "Sega Mega Drive / Genesis" only differs from the name in spacing.
    assert all("/ " not in name for name in names)
    assert resolve_platform_name("genesis") not in names


def test_skips_a_name_that_belongs_to_another_platform() -> None:
    assert "Nintendo Entertainment System" not in platform_alternative_names("famicom")
    assert "Commodore VIC-20" not in platform_alternative_names("c-plus-4")


def test_unknown_slug_has_no_names() -> None:
    assert platform_alternative_names("my-console") == ()
    assert platform_abbreviation("my-console") == ""


def test_igdb_alternative_name_comes_first() -> None:
    entry = {**IGDB_PLATFORM_LIST[UPS.GENESIS], "alternative_name": "MD"}
    with patch.dict(IGDB_PLATFORM_LIST, {UPS.GENESIS: entry}):
        assert platform_alternative_names("genesis")[0] == "MD"


def test_screenscraper_alternative_names_follow_igdbs() -> None:
    igdb_entry = {**IGDB_PLATFORM_LIST[UPS.GENESIS], "alternative_name": "MD"}
    ss_entry = {
        **SCREENSAVER_PLATFORM_LIST[UPS.GENESIS],
        "alternative_names": ["Mega Drive", "md", "Nintendo Entertainment System"],
    }
    with (
        patch.dict(IGDB_PLATFORM_LIST, {UPS.GENESIS: igdb_entry}),
        patch.dict(SCREENSAVER_PLATFORM_LIST, {UPS.GENESIS: ss_entry}),
    ):
        names = platform_alternative_names("genesis")

    # "md" repeats IGDB's name, and NES's own name is skipped.
    assert names[:2] == ("MD", "Mega Drive")
    assert "md" not in names
    assert "Nintendo Entertainment System" not in names
