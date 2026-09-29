"""The gallery "matched" filter, the provider filter and `Rom.is_identified`
read match ids alike, so a ROM the API reports as identified is the one the
filters return."""

from typing import Any

import pytest
from sqlalchemy import String
from sqlalchemy.orm.attributes import InstrumentedAttribute

from handler.database import db_rom_handler
from models.rom import METADATA_SOURCE_COLUMNS, Rom
from models.user import User


def _match_value(column: InstrumentedAttribute[Any]) -> int | str:
    return "match-1" if isinstance(column.type, String) else 123


def _blank_value(column: InstrumentedAttribute[Any]) -> int | str:
    return "" if isinstance(column.type, String) else 0


def _matched_ids(user: User, matched: bool) -> set[int]:
    return {
        r.id for r in db_rom_handler.get_roms_scalar(user_id=user.id, matched=matched)
    }


@pytest.mark.parametrize("source", sorted(METADATA_SOURCE_COLUMNS))
def test_every_source_identifies_in_both_views(source: str, rom: Rom, admin_user: User):
    column = METADATA_SOURCE_COLUMNS[source]
    stored = db_rom_handler.update_rom(rom.id, {column.key: _match_value(column)})

    assert stored.is_identified is True
    assert rom.id in _matched_ids(admin_user, matched=True)
    assert rom.id not in _matched_ids(admin_user, matched=False)


@pytest.mark.parametrize("source", sorted(METADATA_SOURCE_COLUMNS))
def test_blank_id_is_unidentified_in_both_views(
    source: str, rom: Rom, admin_user: User
):
    column = METADATA_SOURCE_COLUMNS[source]
    stored = db_rom_handler.update_rom(rom.id, {column.key: _blank_value(column)})

    assert stored.is_unidentified is True
    assert rom.id in _matched_ids(admin_user, matched=False)
    assert rom.id not in _matched_ids(admin_user, matched=True)


def test_rom_without_ids_is_unidentified_in_both_views(rom: Rom, admin_user: User):
    stored = db_rom_handler.get_rom(rom.id)
    assert stored is not None

    assert stored.is_unidentified is True
    assert rom.id in _matched_ids(admin_user, matched=False)
    assert rom.id not in _matched_ids(admin_user, matched=True)


def test_artwork_only_sgdb_does_not_identify(rom: Rom, admin_user: User):
    stored = db_rom_handler.update_rom(rom.id, {"sgdb_id": 42})

    assert stored.is_unidentified is True
    assert rom.id not in _matched_ids(admin_user, matched=True)


def _provider_ids(user: User, source: str) -> set[int]:
    return {
        r.id
        for r in db_rom_handler.get_roms_scalar(
            user_id=user.id, metadata_providers=[source]
        )
    }


@pytest.mark.parametrize("source", sorted(METADATA_SOURCE_COLUMNS))
def test_provider_filter_agrees_with_matched_filter(
    source: str, rom: Rom, admin_user: User
):
    column = METADATA_SOURCE_COLUMNS[source]

    db_rom_handler.update_rom(rom.id, {column.key: _blank_value(column)})
    assert rom.id not in _provider_ids(admin_user, source)
    assert rom.id in _matched_ids(admin_user, matched=False)

    db_rom_handler.update_rom(rom.id, {column.key: _match_value(column)})
    assert rom.id in _provider_ids(admin_user, source)
    assert rom.id in _matched_ids(admin_user, matched=True)
