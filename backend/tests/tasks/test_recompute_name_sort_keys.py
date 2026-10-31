import json

import pytest
from tests.factories import make_rom

from config.config_manager import config_manager as cm
from handler.database import db_rom_handler
from handler.redis_handler import sync_cache
from models.platform import Platform
from models.rom import compute_name_sort_key
from tasks.manual.recompute_name_sort_keys import (
    APPLIED_SORT_ARTICLES_KEY,
    applied_sort_articles,
    recompute_name_sort_keys_task,
)


def stored_sort_key(rom_id: int) -> str | None:
    rom = db_rom_handler.get_rom(rom_id)
    assert rom is not None
    return rom.name_sort_key


@pytest.fixture(autouse=True)
def clear_applied_articles():
    sync_cache.delete(APPLIED_SORT_ARTICLES_KEY)
    yield
    sync_cache.delete(APPLIED_SORT_ARTICLES_KEY)


def test_unrecorded_articles_are_every_launchbox_article():
    assert "die" in applied_sort_articles()


async def test_derived_keys_follow_the_configured_articles(platform: Platform):
    # Derived with every LaunchBox article, as before an articles list was recorded.
    rom = make_rom(platform, "Die Hard Arcade", name_sort_key=None)
    db_rom_handler.update_rom(rom.id, {"name_sort_key": "hard arcade"})

    stats = await recompute_name_sort_keys_task.run()

    assert stored_sort_key(rom.id) == "die hard arcade"
    assert stats["sort_keys_replaced"] == 1
    applied = sync_cache.get(APPLIED_SORT_ARTICLES_KEY)
    assert applied is not None
    assert json.loads(applied) == ["the", "a", "an"]


async def test_a_custom_sort_key_is_kept(platform: Platform):
    rom = make_rom(platform, "Die Hard Arcade", name_sort_key=None)
    db_rom_handler.update_rom(rom.id, {"name_sort_key": "arcade die hard"})

    await recompute_name_sort_keys_task.run()

    assert stored_sort_key(rom.id) == "arcade die hard"


async def test_a_changed_articles_list_rederives_from_the_recorded_one(
    platform: Platform, mocker
):
    rom = make_rom(platform, "Die Siedler", name_sort_key=None)
    sync_cache.set(APPLIED_SORT_ARTICLES_KEY, json.dumps(["the", "a", "an"]))
    mocker.patch.object(cm.config, "SORT_ARTICLES", ["der", "die", "das"])
    assert stored_sort_key(rom.id) == compute_name_sort_key(
        "Die Siedler", articles=("the", "a", "an")
    )

    await recompute_name_sort_keys_task.run()

    assert stored_sort_key(rom.id) == "siedler"
