"""Searching the gallery by a provider's alternative titles."""

from typing import Any

import pytest
from sqlalchemy import select
from tests.conftest import session as session_factory
from tests.sql_dialects import MARIADB_DIALECT, POSTGRESQL_DIALECT, compile_sql

from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom


def _add_rom(platform: Platform, name: str, **metadata: dict[str, Any]) -> Rom:
    fs_name = f"{name.replace(' ', '_')}.zip"
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=name.lower().replace(" ", "-"),
            fs_name=fs_name,
            fs_name_no_tags=fs_name.removesuffix(".zip"),
            fs_name_no_ext=fs_name.removesuffix(".zip"),
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            **metadata,
        )
    )


def _search_ids(term: str) -> list[int]:
    return [r.id for r in db_rom_handler.get_roms_scalar(search_term=term)]


def _stored_titles(rom: Rom) -> str | None:
    with session_factory() as session:
        return session.scalar(select(Rom.search_titles).where(Rom.id == rom.id))


@pytest.fixture
def ff9(platform: Platform) -> Rom:
    return _add_rom(
        platform,
        "Final Fantasy IX",
        igdb_metadata={"alternative_names": ["FF9", "Final Fantasy 9"]},
    )


@pytest.fixture
def unrelated(platform: Platform) -> Rom:
    return _add_rom(platform, "Chrono Cross")


@pytest.mark.parametrize(
    "term",
    [
        # Every word long enough for the FULLTEXT index on MariaDB and MySQL.
        "ff9",
        "FF9",
        # "9" is too short for it, so this one takes the ILIKE fallback.
        "final fantasy 9",
    ],
)
def test_an_alternative_title_finds_the_rom(ff9: Rom, unrelated: Rom, term: str):
    assert _search_ids(term) == [ff9.id]


def test_the_name_still_finds_the_rom(ff9: Rom, unrelated: Rom):
    assert _search_ids("final fantasy ix") == [ff9.id]


@pytest.mark.parametrize(
    ("column", "key"),
    [
        ("igdb_metadata", "alternative_names"),
        ("moby_metadata", "alternate_titles"),
        ("ss_metadata", "alternative_names"),
        ("manual_metadata", "alternative_names"),
    ],
)
def test_each_provider_contributes_its_titles(
    platform: Platform, unrelated: Rom, column: str, key: str
):
    rom = _add_rom(platform, "Seiken Densetsu", **{column: {key: ["Secret of Mana"]}})

    assert _search_ids("secret of mana") == [rom.id]


def test_titles_from_every_provider_are_searchable_together(platform: Platform):
    rom = _add_rom(
        platform,
        "Final Fantasy IX",
        igdb_metadata={"alternative_names": ["FF9"]},
        ss_metadata={"alternative_names": ["FFIX"]},
    )

    assert _search_ids("ff9") == [rom.id]
    assert _search_ids("ffix") == [rom.id]


def test_a_rom_without_titles_stores_only_its_name(platform: Platform):
    rom = _add_rom(
        platform,
        "Chrono Trigger",
        igdb_metadata={"alternative_names": []},
        moby_metadata={"alternate_titles": "not a list"},
    )

    assert _stored_titles(rom) == "\x1fchrono trigger\x1f"


def test_the_titles_are_stored_folded(platform: Platform):
    rom = _add_rom(
        platform,
        "Final Fantasy IX",
        igdb_metadata={"alternative_names": ["FF9", "Final Fantasy 9"]},
        ss_metadata={"alternative_names": ["FFIX"]},
    )

    assert _stored_titles(rom) == (
        "\x1ffinal fantasy ix\x1fff9\x1ffinal fantasy 9\x1fffix\x1f"
    )


@pytest.mark.parametrize(
    ("alias", "term"),
    [
        # JSON stores these characters escaped, which the titles must not keep.
        ("ŌKAMI Den", "ōkami den"),
        ("Chrono\tTrigger", "chrono trigger"),
        ('Say "Cheese"', 'say "cheese"'),
    ],
)
def test_an_alias_with_an_escaped_character_finds_the_rom(
    platform: Platform, unrelated: Rom, alias: str, term: str
):
    rom = _add_rom(platform, "Name", igdb_metadata={"alternative_names": [alias]})

    assert _search_ids(term) == [rom.id]


@pytest.mark.parametrize("term", ['"', ",", "["])
def test_json_punctuation_matches_nothing(ff9: Rom, term: str):
    assert _search_ids(term) == []


def test_updating_the_metadata_refreshes_the_aliases(ff9: Rom):
    db_rom_handler.update_rom(
        ff9.id, {"igdb_metadata": {"alternative_names": ["Final Fantasy Nine"]}}
    )

    assert _search_ids("nine") == [ff9.id]
    assert _search_ids("ff9") == []


def test_a_hand_added_title_finds_the_rom(ff9: Rom, unrelated: Rom):
    db_rom_handler.update_rom(
        ff9.id, {"manual_metadata": {"alternative_names": ["Пісня кристалів"]}}
    )

    assert _search_ids("пісня кристалів") == [ff9.id]
    assert _search_ids("ff9") == [ff9.id]


def test_the_mariadb_search_matches_the_titles_column_in_one_fulltext_index():
    query = db_rom_handler._filter_by_search_term(select(Rom.id), "ff9")

    assert "MATCH (roms.name, roms.fs_name, roms.search_titles)" in compile_sql(
        query, MARIADB_DIALECT
    )


def test_the_postgresql_search_matches_the_titles_column():
    query = db_rom_handler._filter_by_search_term(select(Rom.id), "ff9")

    assert "roms.search_titles ILIKE" in compile_sql(query, POSTGRESQL_DIALECT)
