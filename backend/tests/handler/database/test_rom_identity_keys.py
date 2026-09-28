"""Checks for the `rom_identity_keys` mirror that backs the `sibling_roms` view.

Migration 0127 moved sibling matching off an OR-of-equalities self-join over
`roms` and onto one row per (ROM, provider it has an id for), maintained by
triggers on `roms` rather than by application code. These tests write through
the normal handlers and assert both the key rows and the view follow.
"""

import pytest
from sqlalchemy import String, select

from handler.database import db_rom_handler
from handler.database.base_handler import sync_session
from models.platform import Platform
from models.rom import (
    IDENTITY_ID_FIELDS,
    Rom,
    RomIdentityKey,
    SiblingRom,
)
from models.user import User

# `flashpoint_id` is a varchar column, the other ids are integers, so a
# parametrized test has to hand each one a value its column accepts.
_STRING_ID_FIELDS = frozenset(
    field
    for field in IDENTITY_ID_FIELDS
    if isinstance(Rom.__table__.c[field].type, String)
)


def _sample_id(field: str, value: int) -> int | str:
    return str(value) if field in _STRING_ID_FIELDS else value


def _add_rom(platform: Platform, name: str, **identity_ids: int | str) -> Rom:
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=name,
            fs_name=f"{name}.zip",
            fs_name_no_tags=name,
            fs_name_no_ext=name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            **identity_ids,
        )
    )


def _keys(rom_id: int) -> set[tuple[int, int, str]]:
    """The (provider code, platform_id, provider_id) rows the triggers wrote.

    `provider_id` is the varchar every provider's id is cast into.
    """
    with sync_session.begin() as session:
        return {
            tuple(row)
            for row in session.execute(
                select(
                    RomIdentityKey.provider,
                    RomIdentityKey.platform_id,
                    RomIdentityKey.provider_id,
                ).where(RomIdentityKey.rom_id == rom_id)
            ).all()
        }


def _view_rows(rom_id: int) -> list[int]:
    """Raw `sibling_roms` rows, undeduped: the view emits one per match."""
    with sync_session.begin() as session:
        return sorted(
            session.scalars(
                select(SiblingRom.sibling_rom_id).where(SiblingRom.rom_id == rom_id)
            ).all()
        )


def _siblings(rom_id: int, user_id: int) -> list[int]:
    with sync_session.begin() as session:
        buckets = db_rom_handler.get_siblings_for_roms(
            [rom_id], user_id=user_id, session=session
        )
        return sorted(sibling.id for sibling, _ in buckets[rom_id])


class TestRomIdentityKeys:
    def test_insert_writes_one_key_per_matched_provider(self, platform: Platform):
        rom = _add_rom(platform, "scraped", igdb_id=11, ss_id=22)

        assert _keys(rom.id) == {
            (IDENTITY_ID_FIELDS.index("igdb_id"), platform.id, "11"),
            (IDENTITY_ID_FIELDS.index("ss_id"), platform.id, "22"),
        }

    def test_unscraped_rom_has_no_keys_and_no_siblings(
        self, admin_user: User, platform: Platform
    ):
        first = _add_rom(platform, "unscraped_a")
        second = _add_rom(platform, "unscraped_b")

        assert _keys(first.id) == set()
        assert _siblings(first.id, admin_user.id) == []
        assert _siblings(second.id, admin_user.id) == []

    @pytest.mark.parametrize("field", IDENTITY_ID_FIELDS)
    def test_each_provider_matches_on_its_own(
        self, admin_user: User, platform: Platform, field: str
    ):
        """Guards the trigger's provider list against the view's.

        Appending to `IDENTITY_ID_FIELDS` without a migration that backfills
        and matches on the new provider fails here.
        """
        value = _sample_id(field, 4242)
        first = _add_rom(platform, f"{field}_a", **{field: value})
        second = _add_rom(platform, f"{field}_b", **{field: value})

        assert _siblings(first.id, admin_user.id) == [second.id]
        assert _siblings(second.id, admin_user.id) == [first.id]

    def test_ids_from_different_providers_do_not_collide(
        self, admin_user: User, platform: Platform
    ):
        """The provider is part of the key, so `igdb_id = 5` is not `ss_id = 5`."""
        igdb = _add_rom(platform, "igdb_five", igdb_id=5)
        ss = _add_rom(platform, "ss_five", ss_id=5)

        assert _siblings(igdb.id, admin_user.id) == []
        assert _siblings(ss.id, admin_user.id) == []

    def test_same_id_on_another_platform_is_not_a_sibling(
        self, admin_user: User, platform: Platform, other_platform: Platform
    ):
        here = _add_rom(platform, "here", igdb_id=77)
        there = _add_rom(other_platform, "there", igdb_id=77)

        assert _siblings(here.id, admin_user.id) == []
        assert _siblings(there.id, admin_user.id) == []

    def test_pair_matching_two_providers_surfaces_once(
        self, admin_user: User, platform: Platform
    ):
        """The view emits a row per matching provider; the API must not."""
        first = _add_rom(platform, "twice_a", igdb_id=9, ss_id=9)
        second = _add_rom(platform, "twice_b", igdb_id=9, ss_id=9)

        assert _view_rows(first.id) == [second.id, second.id]
        assert _siblings(first.id, admin_user.id) == [second.id]

        loaded = db_rom_handler.get_rom(first.id)
        assert loaded is not None
        assert [sibling.id for sibling in loaded.sibling_roms] == [second.id]

    def test_metadata_refresh_moves_the_keys(
        self, admin_user: User, platform: Platform
    ):
        """`update_rom` is a Core-level UPDATE, so only the trigger covers it."""
        rom = _add_rom(platform, "refreshed", igdb_id=100)
        old_match = _add_rom(platform, "old_match", igdb_id=100)
        new_match = _add_rom(platform, "new_match", igdb_id=200)

        db_rom_handler.update_rom(rom.id, {"igdb_id": 200})

        assert _keys(rom.id) == {
            (IDENTITY_ID_FIELDS.index("igdb_id"), platform.id, "200")
        }
        assert _siblings(rom.id, admin_user.id) == [new_match.id]
        assert _siblings(old_match.id, admin_user.id) == []

    def test_clearing_an_id_drops_the_key(self, admin_user: User, platform: Platform):
        rom = _add_rom(platform, "cleared", igdb_id=300)
        other = _add_rom(platform, "still_matched", igdb_id=300)

        db_rom_handler.update_rom(rom.id, {"igdb_id": None})

        assert _keys(rom.id) == set()
        assert _siblings(rom.id, admin_user.id) == []
        assert _siblings(other.id, admin_user.id) == []

    def test_moving_a_rom_moves_its_keys(
        self, admin_user: User, platform: Platform, other_platform: Platform
    ):
        rom = _add_rom(platform, "moved", igdb_id=400)
        left_behind = _add_rom(platform, "left_behind", igdb_id=400)

        db_rom_handler.update_rom(rom.id, {"platform_id": other_platform.id})

        assert _keys(rom.id) == {
            (IDENTITY_ID_FIELDS.index("igdb_id"), other_platform.id, "400")
        }
        assert _siblings(rom.id, admin_user.id) == []
        assert _siblings(left_behind.id, admin_user.id) == []

    def test_delete_cascades(self, platform: Platform):
        rom = _add_rom(platform, "deleted", igdb_id=500)
        rom_id = rom.id

        db_rom_handler.delete_rom(rom_id)

        assert _keys(rom_id) == set()

    def test_update_touching_no_identity_id_skips_the_resync(self, platform: Platform):
        """The `<=>` guard: without it every rom write pays a full resync."""
        rom = _add_rom(platform, "guarded", igdb_id=600)
        marker = (IDENTITY_ID_FIELDS.index("tgdb_id"), platform.id, "999999")
        with sync_session.begin() as session:
            session.add(
                RomIdentityKey(
                    provider=marker[0],
                    platform_id=marker[1],
                    provider_id=marker[2],
                    rom_id=rom.id,
                )
            )

        db_rom_handler.update_rom(rom.id, {"fs_size_bytes": 1234})
        assert marker in _keys(rom.id)

        db_rom_handler.update_rom(rom.id, {"igdb_id": 601})
        assert marker not in _keys(rom.id)

    def test_hidden_siblings_are_excluded(self, admin_user: User, platform: Platform):
        rom = _add_rom(platform, "visible", igdb_id=700)
        hidden_rom = _add_rom(platform, "hidden_rom", igdb_id=700)

        with sync_session.begin() as session:
            buckets = db_rom_handler.get_siblings_for_roms(
                [rom.id],
                user_id=admin_user.id,
                session=session,
                hidden_rom_ids=[hidden_rom.id],
            )
            assert buckets[rom.id] == []

        with sync_session.begin() as session:
            buckets = db_rom_handler.get_siblings_for_roms(
                [rom.id],
                user_id=admin_user.id,
                session=session,
                hidden_platform_ids=[platform.id],
            )
            assert buckets[rom.id] == []

    def test_is_main_sibling_resolves_per_user(
        self, admin_user: User, platform: Platform
    ):
        rom = _add_rom(platform, "main_a", igdb_id=800)
        sibling = _add_rom(platform, "main_b", igdb_id=800)
        rom_user = db_rom_handler.add_rom_user(rom_id=sibling.id, user_id=admin_user.id)
        db_rom_handler.update_rom_user(rom_user.id, {"is_main_sibling": True})

        with sync_session.begin() as session:
            buckets = db_rom_handler.get_siblings_for_roms(
                [rom.id], user_id=admin_user.id, session=session
            )
            assert [(s.id, is_main) for s, is_main in buckets[rom.id]] == [
                (sibling.id, True)
            ]


class TestIdentityKeyStatistics:
    """Migration 0127 samples this table right after its backfill, which a fresh
    install runs while the table is still empty. The scan that fills it has to
    resample, or the optimizer keeps the plan it chose for an empty table.
    """

    def test_resampling_leaves_the_keys_readable(self, platform: Platform):
        """Runs the real statement, so each engine's CI leg proves its own syntax."""
        rom = _add_rom(platform, "sampled", igdb_id=99)

        db_rom_handler.refresh_identity_key_statistics()

        assert _keys(rom.id) == {
            (IDENTITY_ID_FIELDS.index("igdb_id"), platform.id, "99")
        }

    def test_resampling_an_empty_table_is_not_an_error(self) -> None:
        """A fresh install resamples after a scan that found nothing."""
        db_rom_handler.refresh_identity_key_statistics()
