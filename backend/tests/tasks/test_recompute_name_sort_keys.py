import json

import pytest
from rq.job import JOB_ID_PATTERN
from tests.factories import make_rom

from config.config_manager import config_manager as cm
from handler.database import db_rom_handler
from handler.database.roms_handler import DBRomsHandler
from handler.redis_handler import sync_cache
from models.platform import Platform
from tasks.manual.recompute_name_sort_keys import (
    APPLIED_SORT_ARTICLES_KEY,
    applied_sort_articles,
    articles_digest,
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


def test_no_articles_are_recorded_until_a_recompute_runs():
    assert applied_sort_articles() is None


async def test_derived_keys_follow_the_configured_articles(platform: Platform):
    rom = make_rom(platform, "Die Hard Arcade")
    db_rom_handler.update_rom(
        rom.id, {"name_sort_key": "hard arcade", "name_sort_key_custom": False}
    )

    stats = await recompute_name_sort_keys_task.run()

    assert stored_sort_key(rom.id) == "die hard arcade"
    assert stats["sort_keys_replaced"] == 1
    applied = sync_cache.get(APPLIED_SORT_ARTICLES_KEY)
    assert applied is not None
    assert json.loads(applied) == ["the", "a", "an"]


async def test_a_custom_sort_key_is_kept(platform: Platform):
    rom = make_rom(platform, "Die Hard Arcade")
    db_rom_handler.update_rom(rom.id, {"name_sort_key": "hard arcade"})

    await recompute_name_sort_keys_task.run()

    assert stored_sort_key(rom.id) == "hard arcade"


async def test_a_changed_articles_list_rederives_derived_keys(
    platform: Platform, mocker
):
    rom = make_rom(platform, "Die Siedler")
    assert stored_sort_key(rom.id) == "die siedler"
    mocker.patch.object(cm.config, "SORT_ARTICLES", ["der", "die", "das"])

    await recompute_name_sort_keys_task.run()

    assert stored_sort_key(rom.id) == "siedler"


def test_a_key_is_not_replaced_once_its_name_changed(platform: Platform):
    rom = make_rom(platform, "Die Hard Arcade")
    db_rom_handler.update_rom(rom.id, {"name": "Die Hard Trilogy"})

    replaced = db_rom_handler.replace_derived_sort_keys(
        {rom.id: ("Die Hard Arcade", "die hard arcade")}
    )

    assert replaced == 0
    assert stored_sort_key(rom.id) == "die hard trilogy"


async def test_replacing_keys_drops_the_cached_gallery_order(
    platform: Platform, mocker
):
    rom = make_rom(platform, "Die Hard Arcade")
    db_rom_handler.update_rom(
        rom.id, {"name_sort_key": "hard arcade", "name_sort_key_custom": False}
    )
    invalidate = mocker.patch.object(DBRomsHandler, "invalidate_filter_values_cache")

    await recompute_name_sort_keys_task.run()

    invalidate.assert_called_once()


def test_an_accent_only_rename_still_blocks_the_replacement(platform: Platform):
    rom = make_rom(platform, "Die Hard Arcade")
    db_rom_handler.update_rom(rom.id, {"name": "Díe Hard Arcade"})

    replaced = db_rom_handler.replace_derived_sort_keys(
        {rom.id: ("Die Hard Arcade", "die hard arcade")}
    )

    assert replaced == 0


async def test_a_run_that_fails_partway_leaves_no_articles_recorded(
    platform: Platform, mocker
):
    rom = make_rom(platform, "Die Hard Arcade")
    db_rom_handler.update_rom(
        rom.id, {"name_sort_key": "hard arcade", "name_sort_key_custom": False}
    )
    sync_cache.set(APPLIED_SORT_ARTICLES_KEY, json.dumps(["the", "a", "an"]))
    mocker.patch.object(
        DBRomsHandler, "replace_derived_sort_keys", side_effect=RuntimeError("db down")
    )

    with pytest.raises(RuntimeError):
        await recompute_name_sort_keys_task.run()

    assert applied_sort_articles() is None


def test_each_articles_list_gets_its_own_valid_job_id():
    english = articles_digest(("the", "a", "an"))
    german = articles_digest(("der", "die", "das"))

    assert english != german
    assert JOB_ID_PATTERN.fullmatch(f"recompute_name_sort_keys_bootstrap_{english}")
