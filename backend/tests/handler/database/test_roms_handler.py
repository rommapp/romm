"""Unit tests for DBRomsHandler's derived-column bookkeeping.

Bulk `update()` bypasses the ORM `@validates` hooks, so `update_rom` keeps
the columns derived from `name` / `fs_name` / `fs_path` in sync explicitly.
"""

import re
import struct
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Dialect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from tests.factories import make_rom, make_save, make_state
from tests.sql_dialects import MARIADB_DIALECT, POSTGRESQL_DIALECT, compile_sql

from decorators.database import INJECTED_SESSION
from exceptions.database_exceptions import RomFileOwnerChangedError
from handler.database import db_platform_handler, db_rom_handler
from handler.database.base_handler import sync_engine, sync_session
from handler.database.roms_handler import _filter_values_cache_version
from models.assets import Save, State
from models.platform import Platform
from models.rom import (
    HAS_FILE_ON_DISK_FILTERS,
    Rom,
    RomFile,
    RomFileCategory,
    TrackMeta,
    compute_full_path_hash,
)
from models.user import User


class TestUpdateRomDerivedColumns:
    def test_update_name_resyncs_name_sort_key(self, rom: Rom):
        updated = db_rom_handler.update_rom(rom.id, {"name": "The New Name 2"})

        assert updated.name == "The New Name 2"
        assert updated.name_sort_key == "new name 000000000002"

    def test_update_fs_name_resyncs_all_parts(self, rom: Rom):
        updated = db_rom_handler.update_rom(rom.id, {"fs_name": "Sonic (Europe).md"})

        assert updated.fs_name == "Sonic (Europe).md"
        assert updated.fs_name_no_tags == "Sonic"
        assert updated.fs_name_no_ext == "Sonic (Europe)"
        # The extension is resynced too; the rename endpoint used to omit it.
        assert updated.fs_extension == "md"

    def test_update_either_path_half_resyncs_the_digest(self, rom: Rom):
        updated = db_rom_handler.update_rom(rom.id, {"fs_name": "Sonic (Europe).md"})
        assert updated.full_path_hash == compute_full_path_hash(
            rom.fs_path, "Sonic (Europe).md"
        )

        # The half the caller left out comes from the stored row.
        moved = db_rom_handler.update_rom(rom.id, {"fs_path": "test/roms/Hacks"})
        assert moved.full_path_hash == compute_full_path_hash(
            "test/roms/Hacks", "Sonic (Europe).md"
        )

    def test_update_unrelated_field_leaves_derived_columns(self, rom: Rom):
        updated = db_rom_handler.update_rom(rom.id, {"summary": "just a summary"})

        assert updated.summary == "just a summary"
        assert updated.fs_name_no_tags == "test_rom"
        assert updated.fs_extension == "zip"
        assert updated.name_sort_key == "test_rom"

    def test_explicit_name_sort_key_marks_custom(self, rom: Rom):
        updated = db_rom_handler.update_rom(rom.id, {"name_sort_key": "zelda"})

        assert updated.name_sort_key == "zelda"

    def test_update_name_keeps_custom_sort_key(self, rom: Rom):
        db_rom_handler.update_rom(rom.id, {"name_sort_key": "pinned"})
        updated = db_rom_handler.update_rom(rom.id, {"name": "The New Name 2"})

        # A pinned custom key is never clobbered by a name change.
        assert updated.name == "The New Name 2"
        assert updated.name_sort_key == "pinned"


class TestAddRomMergesScannedTags:
    """`add_rom` merges the partially-populated Rom that `scan_rom` returns.

    A rescan re-reads the filename tags onto the existing row and relies on this
    merge to persist them, so the tag columns have to survive the round trip
    while columns the scan never names keep their stored values.
    """

    def _scanned(self, rom: Rom) -> Rom:
        """The subset of columns `scan_rom` rebuilds for an existing entry."""
        return Rom(
            id=rom.id,
            platform_id=rom.platform_id,
            fs_name=rom.fs_name,
            fs_path=rom.fs_path,
            regions=["USA"],
            revision="A",
            version="1.1",
            languages=["English"],
            tags=["Proto"],
        )

    def test_tag_columns_are_persisted(self, rom: Rom):
        db_rom_handler.update_rom(
            rom.id,
            {
                "regions": ["us"],
                "languages": ["en"],
                "tags": ["proto"],
                "revision": "",
                "version": "",
            },
        )

        db_rom_handler.add_rom(self._scanned(rom))  # noqa: TID251

        stored = db_rom_handler.get_rom(rom.id)
        assert stored is not None
        assert stored.regions == ["USA"]
        assert stored.languages == ["English"]
        assert stored.tags == ["Proto"]
        assert stored.revision == "A"
        assert stored.version == "1.1"

    def test_columns_the_scan_omits_are_left_alone(self, rom: Rom):
        db_rom_handler.update_rom(rom.id, {"summary": "kept", "slug": "kept-slug"})

        db_rom_handler.add_rom(self._scanned(rom))  # noqa: TID251

        stored = db_rom_handler.get_rom(rom.id)
        assert stored is not None
        assert stored.summary == "kept"
        assert stored.slug == "kept-slug"


class TestUniquePlatformFullPath:
    """A folder can't hold two entries with the same name, so the DB rejects a
    second ROM at the same full path (via its `full_path_hash`). This is what
    stops racing scans (e.g. after the patcher uploads a patched ROM) from
    creating duplicate library entries."""

    def test_duplicate_platform_full_path_rejected(self, platform: Platform):
        make_rom(platform, "Patched Game", fs_extension="gba")

        with pytest.raises(IntegrityError):
            make_rom(platform, "Patched Game", fs_extension="gba")

    def test_same_fs_name_in_another_folder_allowed(self, platform: Platform):
        """What a custom library structure makes ordinary, and what the old
        (platform_id, fs_name) index forbade."""
        root = make_rom(platform, "Patched Game", fs_extension="gba")
        nested = make_rom(
            platform,
            "Patched Game",
            fs_extension="gba",
            fs_path=f"{platform.slug}/roms/Hacks",
        )

        assert nested.id != root.id

    def test_moving_a_rom_onto_an_occupied_path_is_rejected(self, platform: Platform):
        """`update_rom` bypasses the ORM, so it has to resync the digest the
        unique index reads or the collision goes unnoticed."""
        make_rom(platform, "Patched Game", fs_extension="gba")
        moved = make_rom(
            platform,
            "Other Game",
            fs_extension="gba",
            fs_path=f"{platform.slug}/roms/Hacks",
        )

        with pytest.raises(IntegrityError):
            db_rom_handler.update_rom(
                moved.id,
                {"fs_path": f"{platform.slug}/roms", "fs_name": "Patched Game.gba"},
            )

    def test_same_fs_name_other_platform_allowed(self, platform: Platform):
        other = db_platform_handler.add_platform(
            Platform(name="other", slug="other_slug", fs_slug="other_slug")
        )

        first = make_rom(platform, "Patched Game", fs_extension="gba")
        second = make_rom(other, "Patched Game", fs_extension="gba")

        assert first.id != second.id


class TestHasSavesStatesFilter:
    """The has-saves / has-states filters match a user's own assets plus other
    users' public (community) ones, mirroring the shared-assets visibility."""

    def _add_save(self, rom: Rom, user: User, *, is_public: bool) -> Save:
        return make_save(
            rom,
            user,
            "filter.sav",
            file_path=f"{rom.fs_path}/saves",
            file_size_bytes=1,
            is_public=is_public,
        )

    def _add_state(self, rom: Rom, user: User, *, is_public: bool) -> State:
        return make_state(
            rom,
            user,
            "filter.state",
            file_path=f"{rom.fs_path}/states",
            file_size_bytes=1,
            is_public=is_public,
        )

    def _rom_ids(self, **kwargs) -> set[int]:
        return {r.id for r in db_rom_handler.get_roms_scalar(**kwargs)}

    # ---- saves ----

    def test_own_save_matches(self, rom: Rom, admin_user: User):
        self._add_save(rom, admin_user, is_public=False)
        assert rom.id in self._rom_ids(user_id=admin_user.id, has_saves=True)

    def test_other_users_private_save_does_not_match(
        self, rom: Rom, admin_user: User, editor_user: User
    ):
        self._add_save(rom, editor_user, is_public=False)
        assert rom.id not in self._rom_ids(user_id=admin_user.id, has_saves=True)

    def test_other_users_public_save_matches(
        self, rom: Rom, admin_user: User, editor_user: User
    ):
        self._add_save(rom, editor_user, is_public=True)
        assert rom.id in self._rom_ids(user_id=admin_user.id, has_saves=True)

    def test_has_saves_false_excludes_public(
        self, rom: Rom, admin_user: User, editor_user: User
    ):
        self._add_save(rom, editor_user, is_public=True)
        assert rom.id not in self._rom_ids(user_id=admin_user.id, has_saves=False)

    # ---- states ----

    def test_other_users_public_state_matches(
        self, rom: Rom, admin_user: User, editor_user: User
    ):
        self._add_state(rom, editor_user, is_public=True)
        assert rom.id in self._rom_ids(user_id=admin_user.id, has_states=True)

    def test_other_users_private_state_does_not_match(
        self, rom: Rom, admin_user: User, editor_user: User
    ):
        self._add_state(rom, editor_user, is_public=False)
        assert rom.id not in self._rom_ids(user_id=admin_user.id, has_states=True)


def _scanned_file(
    rom: Rom,
    file_name: str,
    *,
    file_path: str | None = None,
    size: int = 100,
    crc: str | None = "crc",
    md5: str | None = "md5",
    sha1: str | None = "sha1",
    category: RomFileCategory | None = None,
    track_meta: TrackMeta | None = None,
) -> RomFile:
    """A transient RomFile as the filesystem scanner builds it."""
    return RomFile(
        rom_id=rom.id,
        file_name=file_name,
        file_path=file_path if file_path is not None else rom.fs_path,
        file_size_bytes=size,
        crc_hash=crc,
        md5_hash=md5,
        sha1_hash=sha1,
        category=category,
        track_meta=track_meta,
    )


def _sync(rom: Rom, scanned: list[RomFile]) -> list[RomFile]:
    return db_rom_handler.sync_rom_files(rom.id, scanned).files


class TestHasSoundtrackFilter:
    """Smart collections resolve their criteria through `get_roms_scalar`, so
    it must forward has_soundtrack to filter_roms like the other flags."""

    def _with_soundtrack(self, rom: Rom) -> None:
        _sync(
            rom,
            [_scanned_file(rom, "track01.flac", category=RomFileCategory.SOUNDTRACK)],
        )

    def test_has_soundtrack_true_matches_only_roms_with_tracks(
        self, rom: Rom, platform: Platform
    ):
        other = make_rom(platform, "No Music", fs_extension="gba")
        self._with_soundtrack(rom)

        ids = {r.id for r in db_rom_handler.get_roms_scalar(has_soundtrack=True)}

        assert rom.id in ids
        assert other.id not in ids

    def test_has_soundtrack_false_excludes_roms_with_tracks(
        self, rom: Rom, platform: Platform
    ):
        other = make_rom(platform, "No Music", fs_extension="gba")
        self._with_soundtrack(rom)

        ids = {r.id for r in db_rom_handler.get_roms_scalar(has_soundtrack=False)}

        assert rom.id not in ids
        assert other.id in ids


class TestGetRomIds:
    """Pin `get_rom_ids` to `get_roms_scalar`: same ids, same order."""

    def _physical_game(self, platform: Platform) -> Rom:
        return make_rom(
            platform,
            "Physical Game",
            fs_extension="",
            fs_path=f"{platform.slug}/roms/.physical",
            is_physical=True,
        )

    def test_matches_the_orm_accessor_for_every_scope_that_uses_it(
        self,
        rom: Rom,
        platform: Platform,
        other_platform: Platform,
        admin_user: User,
    ) -> None:
        """Pin the two accessors to each other rather than to a fixed list."""
        make_rom(other_platform, "Other Platform", fs_extension="gba")
        self._physical_game(platform)

        for scope in (
            {},
            {"user_id": admin_user.id},
            {"platform_ids": [platform.id]},
            {"hidden_platform_ids": [other_platform.id]},
            {"hidden_rom_ids": [rom.id]},
            {"order_by": "name", "order_dir": "desc"},
            {"platform_ids": [platform.id], **HAS_FILE_ON_DISK_FILTERS},
        ):
            assert db_rom_handler.get_rom_ids(**scope) == [
                r.id for r in db_rom_handler.get_roms_scalar(**scope)
            ], scope

    def test_hidden_rom_drops_out(
        self, rom: Rom, second_rom: Rom, platform: Platform
    ) -> None:
        ids = db_rom_handler.get_rom_ids(
            platform_ids=[platform.id], hidden_rom_ids=[rom.id]
        )

        assert rom.id not in ids
        assert second_rom.id in ids

    def test_physical_game_drops_out(self, rom: Rom, platform: Platform) -> None:
        physical = self._physical_game(platform)

        ids = db_rom_handler.get_rom_ids(
            platform_ids=[platform.id], **HAS_FILE_ON_DISK_FILTERS
        )

        assert physical.id not in ids
        assert rom.id in ids


class TestSyncRomFiles:
    """A rescan reconciles the file rows in place, so ids survive it. Anything
    keyed on a file id (track metadata, persisted soundtrack covers) stays
    valid instead of being orphaned by a purge-and-reinsert."""

    def test_unchanged_file_keeps_its_id(self, rom: Rom):
        first = _sync(rom, [_scanned_file(rom, "a.bin")])
        second = _sync(rom, [_scanned_file(rom, "a.bin")])

        assert [f.id for f in second] == [f.id for f in first]

    def test_changed_metadata_updates_in_place(self, rom: Rom):
        (first,) = _sync(rom, [_scanned_file(rom, "a.bin")])
        (second,) = _sync(rom, [_scanned_file(rom, "a.bin", size=200, sha1="new-sha1")])

        assert second.id == first.id
        reloaded = db_rom_handler.get_rom_file_by_id(first.id)
        assert reloaded is not None
        assert reloaded.file_size_bytes == 200
        assert reloaded.sha1_hash == "new-sha1"

    @pytest.mark.parametrize(
        ("inspected", "size", "mtime", "sigil_title_id", "keep_metadata"),
        [
            pytest.param(False, 200, 1000.0, None, True, id="unchanged-keeps-metadata"),
            pytest.param(False, 300, 1000.0, None, False, id="size-change-clears"),
            pytest.param(False, 200, 2000.0, None, False, id="mtime-change-clears"),
            pytest.param(True, 200, 1000.0, None, False, id="inspected-clears"),
            pytest.param(
                False,
                300,
                1000.0,
                "0100ABCD12345000",
                False,
                id="changed-writes-sigil-id-and-clears-metadata",
            ),
            pytest.param(
                False,
                200,
                1000.0,
                "0100ABCD12345000",
                True,
                id="unchanged-writes-sigil-id-and-keeps-metadata",
            ),
        ],
    )
    def test_converto_metadata_tracks_content_and_inspection(
        self,
        rom: Rom,
        inspected: bool,
        size: int,
        mtime: float,
        sigil_title_id: str | None,
        keep_metadata: bool,
    ):
        metadata = {"title_id": "0100ABCD12340000", "title_version": 65536}
        (first,) = _sync(rom, [_scanned_file(rom, "a.bin")])
        scanned = _scanned_file(rom, "a.bin", size=200)
        scanned.last_modified = 1000.0
        for column, value in metadata.items():
            setattr(scanned, column, value)
        scanned.converto_read_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        (second,) = _sync(rom, [scanned])

        assert second.id == first.id
        stored = db_rom_handler.get_rom_file_by_id(first.id)
        assert stored is not None
        assert {column: getattr(stored, column) for column in metadata} == metadata

        scanned = _scanned_file(rom, "a.bin", size=size, sha1=None)
        scanned.last_modified = mtime
        scanned.title_id = sigil_title_id
        if inspected:
            scanned.converto_read_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
        db_rom_handler.sync_rom_files(rom.id, [scanned])

        stored = db_rom_handler.get_rom_file_by_id(first.id)
        assert stored is not None
        assert stored.file_size_bytes == size
        assert stored.last_modified == mtime
        expected = dict(metadata) if keep_metadata else dict.fromkeys(metadata)
        if sigil_title_id is not None:
            expected["title_id"] = sigil_title_id
        assert {column: getattr(stored, column) for column in metadata} == expected
        assert (stored.converto_read_at is not None) == (keep_metadata or inspected)

    @pytest.mark.parametrize(
        ("stored_mtime", "scanned_mtime", "matching_hashes"),
        [
            pytest.param(
                struct.unpack("f", struct.pack("f", 1700000000.123))[0],
                1700000000.123,
                False,
                id="legacy-single-precision-mtime",
            ),
            pytest.param(1000.0, 2000.0, True, id="matching-content-with-new-mtime"),
        ],
    )
    def test_unread_title_ids_survive_equivalent_content(
        self,
        rom: Rom,
        stored_mtime: float,
        scanned_mtime: float,
        matching_hashes: bool,
    ):
        metadata = {"title_id": "SCUS-94163", "title_version": 1}
        scanned = _scanned_file(
            rom, "game.chd", sha1="sha1" if matching_hashes else None
        )
        scanned.last_modified = stored_mtime
        for column, value in metadata.items():
            setattr(scanned, column, value)
        (first,) = _sync(rom, [scanned])
        scanned = _scanned_file(
            rom, "game.chd", sha1="sha1" if matching_hashes else None
        )
        scanned.last_modified = scanned_mtime

        db_rom_handler.sync_rom_files(rom.id, [scanned])

        stored = db_rom_handler.get_rom_file_by_id(first.id)
        assert stored is not None
        assert stored.last_modified == scanned_mtime
        assert {column: getattr(stored, column) for column in metadata} == metadata

    def test_new_hashes_clear_unread_title_ids_despite_a_kept_mtime(self, rom: Rom):
        scanned = _scanned_file(rom, "game.chd")
        scanned.last_modified = 1000.0
        scanned.title_id = "SCUS-94163"
        (first,) = _sync(rom, [scanned])
        rehashed = _scanned_file(rom, "game.chd", sha1="other-sha1")
        rehashed.last_modified = 1000.0

        db_rom_handler.sync_rom_files(rom.id, [rehashed])

        stored = db_rom_handler.get_rom_file_by_id(first.id)
        assert stored is not None
        assert stored.title_id is None

    def test_retagged_track_meta_is_updated_in_place(self, rom: Rom):
        def scanned(title: str, year: int) -> RomFile:
            return _scanned_file(
                rom,
                "track01.flac",
                category=RomFileCategory.SOUNDTRACK,
                track_meta=TrackMeta(rom_id=rom.id, title=title, year=year),
            )

        (first,) = _sync(rom, [scanned("Green Hill", 1991)])
        _sync(rom, [scanned("Green Hill Zone", 1992)])

        reloaded = db_rom_handler.get_rom_file_by_id(first.id)
        assert reloaded is not None
        assert reloaded.track_meta is not None
        assert reloaded.track_meta.title == "Green Hill Zone"
        assert reloaded.track_meta.year == 1992

    def test_unset_columns_do_not_overwrite_not_null_values(self, rom: Rom):
        """A scanned row leaves unset columns as None, and the model defaults
        only apply on insert. The update path has to skip them rather than
        write NULL into a NOT NULL column."""
        scanned = _scanned_file(rom, "a.bin", size=200)
        _sync(rom, [scanned])

        unset = _scanned_file(rom, "a.bin")
        unset.file_size_bytes = None  # type: ignore[assignment]
        (updated,) = _sync(rom, [unset])

        assert updated.file_size_bytes == 200

    def test_renamed_file_is_matched_by_content(self, rom: Rom):
        (first,) = _sync(rom, [_scanned_file(rom, "a.bin")])
        (second,) = _sync(rom, [_scanned_file(rom, "b.bin")])

        assert second.id == first.id
        assert second.file_name == "b.bin"

    def test_renamed_reused_row_keeps_its_id(self, rom: Rom):
        (first,) = _sync(rom, [_scanned_file(rom, "old.nsp")])
        first.file_name = "new.nsp"

        synced = db_rom_handler.sync_rom_files(rom.id, [first])

        stored = db_rom_handler.get_rom_file_by_id(first.id)
        assert stored is not None
        assert synced.files[0].id == first.id
        assert stored.file_name == "new.nsp"

    def test_moved_file_is_matched_by_content(self, rom: Rom):
        (first,) = _sync(rom, [_scanned_file(rom, "a.bin")])
        (second,) = _sync(
            rom, [_scanned_file(rom, "a.bin", file_path=f"{rom.fs_path}/disc1")]
        )

        assert second.id == first.id
        assert second.file_path == f"{rom.fs_path}/disc1"

    def test_partial_hashes_do_not_match_by_content(self, rom: Rom):
        (first,) = _sync(rom, [_scanned_file(rom, "a.bin", sha1=None)])
        (second,) = _sync(rom, [_scanned_file(rom, "b.bin", sha1=None)])

        # Without all three hashes the rename can't be proven, so a new row wins.
        assert second.id != first.id

    def test_identical_copies_are_not_paired_arbitrarily(self, rom: Rom):
        _sync(rom, [_scanned_file(rom, "a.bin"), _scanned_file(rom, "b.bin")])
        renamed = _sync(rom, [_scanned_file(rom, "c.bin"), _scanned_file(rom, "d.bin")])

        assert {f.file_name for f in renamed} == {"c.bin", "d.bin"}
        assert len(db_rom_handler.rom_files_for_rom_id(rom.id)) == 2

    def test_new_file_is_inserted_and_vanished_file_deleted(self, rom: Rom):
        _sync(
            rom,
            [
                _scanned_file(rom, "a.bin"),
                _scanned_file(rom, "b.bin", crc="crc2", md5="md52", sha1="sha12"),
            ],
        )
        _sync(
            rom,
            [
                _scanned_file(rom, "a.bin"),
                _scanned_file(rom, "c.bin", crc="crc3", md5="md53", sha1="sha13"),
            ],
        )

        assert {f.file_name for f in db_rom_handler.rom_files_for_rom_id(rom.id)} == {
            "a.bin",
            "c.bin",
        }

    def test_track_meta_survives_a_rescan(self, rom: Rom):
        def scanned() -> RomFile:
            return _scanned_file(
                rom,
                "track01.flac",
                file_path=f"{rom.fs_path}/soundtrack",
                category=RomFileCategory.SOUNDTRACK,
                track_meta=TrackMeta(
                    rom_id=rom.id, title="Green Hill", has_embedded_cover=True
                ),
            )

        (first,) = _sync(rom, [scanned()])
        db_rom_handler.upsert_track_meta(
            first.id, rom.id, {"cover_path": "covers/track01.png"}
        )

        synced = db_rom_handler.sync_rom_files(rom.id, [scanned()])

        assert synced.files[0].id == first.id
        assert synced.orphaned_cover_paths == []
        reloaded = db_rom_handler.get_rom_file_by_id(first.id)
        assert reloaded is not None
        assert reloaded.track_meta is not None
        assert reloaded.track_meta.title == "Green Hill"
        # The scanner never reports the cover path, so the persisted one stands.
        assert reloaded.track_meta.cover_path == "covers/track01.png"

    def test_track_meta_dropped_when_file_no_longer_has_tags(self, rom: Rom):
        (first,) = _sync(
            rom,
            [
                _scanned_file(
                    rom,
                    "track01.flac",
                    category=RomFileCategory.SOUNDTRACK,
                    track_meta=TrackMeta(rom_id=rom.id, title="Green Hill"),
                )
            ],
        )
        db_rom_handler.upsert_track_meta(
            first.id, rom.id, {"cover_path": "covers/track01.png"}
        )

        synced = db_rom_handler.sync_rom_files(
            rom.id,
            [_scanned_file(rom, "track01.flac", category=RomFileCategory.GAME)],
        )

        # The cover has nothing pointing at it now, so the caller must unlink it.
        assert synced.orphaned_cover_paths == ["covers/track01.png"]
        reloaded = db_rom_handler.get_rom_file_by_id(first.id)
        assert reloaded is not None
        assert reloaded.track_meta is None

    def test_vanished_soundtrack_reports_its_orphaned_cover(self, rom: Rom):
        (first,) = _sync(
            rom,
            [
                _scanned_file(
                    rom,
                    "track01.flac",
                    category=RomFileCategory.SOUNDTRACK,
                    track_meta=TrackMeta(rom_id=rom.id, title="Green Hill"),
                )
            ],
        )
        db_rom_handler.upsert_track_meta(
            first.id, rom.id, {"cover_path": "covers/track01.png"}
        )

        # Deleting the row cascades the track metadata, taking the only
        # reference to the cover with it.
        synced = db_rom_handler.sync_rom_files(rom.id, [])

        assert synced.files == []
        assert synced.orphaned_cover_paths == ["covers/track01.png"]


class TestScanFileLoaders:
    """The scan loop reads rows off detached roms, so every relationship it
    touches has to be eager-loaded by the lookup."""

    def test_get_roms_by_fs_name_with_files_loads_rows_and_backref(
        self, multi_file_rom: Rom, platform: Platform
    ):
        rom = db_rom_handler.get_roms_by_fs_name(
            platform_id=platform.id, fs_names={multi_file_rom.fs_name}, with_files=True
        )[multi_file_rom.full_path]

        assert {f.file_name for f in rom.files} == {"disc1.bin", "disc2.bin"}
        assert all(f.track_meta is None for f in rom.files)
        assert all(f.rom.fs_name == rom.fs_name for f in rom.files)

    def test_get_roms_by_fs_name_leaves_files_unloaded_by_default(
        self, multi_file_rom: Rom, platform: Platform
    ):
        rom = db_rom_handler.get_roms_by_fs_name(
            platform_id=platform.id, fs_names={multi_file_rom.fs_name}
        )[multi_file_rom.full_path]

        assert "files" in sa_inspect(rom).unloaded

    def test_rom_files_for_rom_id_loads_track_meta(self, multi_file_rom: Rom):
        files = db_rom_handler.rom_files_for_rom_id(multi_file_rom.id)

        assert len(files) == 2
        assert all("track_meta" not in sa_inspect(f).unloaded for f in files)


class TestSyncRomFilesWithReusedRows:
    def test_rows_handed_back_are_a_noop(self, rom: Rom):
        first = _sync(rom, [_scanned_file(rom, "a.bin")])

        second = db_rom_handler.sync_rom_files(rom.id, first).files

        assert [f.id for f in second] == [f.id for f in first]
        assert second[0].md5_hash == "md5"


def _add_rom_file(
    rom: Rom,
    file_name: str = "game.bin",
    size: int = 1000,
    category: RomFileCategory | None = None,
    session: Session = INJECTED_SESSION,
) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=file_name,
            file_path=rom.fs_path,
            file_size_bytes=size,
            category=category,
        ),
        session=session,
    )


class TestRomFileSizeTotal:
    """Check that per-file writes keep the ROM size total in sync."""

    def _size(self, rom: Rom) -> int:
        stored = db_rom_handler.get_rom(rom.id)
        assert stored is not None
        return stored.fs_size_bytes

    def test_add_counts_every_category(self, rom: Rom):
        _add_rom_file(rom, "game.bin", 1000, RomFileCategory.GAME)
        _add_rom_file(rom, "manual.pdf", 200, RomFileCategory.MANUAL)
        _add_rom_file(rom, "guide.txt", 30, RomFileCategory.WALKTHROUGH)

        assert self._size(rom) == 1230

    def test_delete_subtracts_the_file(self, rom: Rom):
        _add_rom_file(rom, "game.bin", 1000, RomFileCategory.GAME)
        manual = _add_rom_file(rom, "manual.pdf", 200, RomFileCategory.MANUAL)

        db_rom_handler.delete_rom_file(manual.id)

        assert self._size(rom) == 1000

    def test_deleting_the_last_file_leaves_zero(self, rom: Rom):
        game = _add_rom_file(rom, "game.bin", 1000, RomFileCategory.GAME)

        db_rom_handler.delete_rom_file(game.id)

        assert self._size(rom) == 0

    def test_resized_file_updates_the_total(self, rom: Rom):
        game = _add_rom_file(rom, "game.bin", 1000, RomFileCategory.GAME)

        db_rom_handler.update_rom_file(game.id, {"file_size_bytes": 4000})

        assert self._size(rom) == 4000

    def test_other_roms_keep_their_total(self, rom: Rom, second_rom: Rom):
        _add_rom_file(second_rom, "other.bin", 500, RomFileCategory.GAME)
        game = _add_rom_file(rom, "game.bin", 1000, RomFileCategory.GAME)

        db_rom_handler.delete_rom_file(game.id)

        assert self._size(second_rom) == 500

    def test_deleting_an_unknown_file_is_a_no_op(self, rom: Rom):
        _add_rom_file(rom, "game.bin", 1000, RomFileCategory.GAME)

        db_rom_handler.delete_rom_file(999_999)

        assert self._size(rom) == 1000

    def test_moving_a_file_updates_both_roms(self, rom: Rom, second_rom: Rom):
        _add_rom_file(rom, "game.bin", 1000, RomFileCategory.GAME)
        manual = _add_rom_file(rom, "manual.pdf", 200, RomFileCategory.MANUAL)

        db_rom_handler.update_rom_file(manual.id, {"rom_id": second_rom.id})

        assert self._size(rom) == 1000
        assert self._size(second_rom) == 200

    def test_merging_a_file_under_another_rom_updates_both(
        self, rom: Rom, second_rom: Rom
    ):
        _add_rom_file(rom, "game.bin", 1000, RomFileCategory.GAME)
        manual = _add_rom_file(rom, "manual.pdf", 200, RomFileCategory.MANUAL)

        db_rom_handler.add_rom_file(
            RomFile(
                id=manual.id,
                rom_id=second_rom.id,
                file_name=manual.file_name,
                file_path=second_rom.fs_path,
                file_size_bytes=manual.file_size_bytes,
                category=manual.category,
            )
        )

        assert self._size(rom) == 1000
        assert self._size(second_rom) == 200


class TestRomFileSizeSidecarInvalidation:
    """The size-sorted rom-id and char indexes are cached under the filter
    values version, so a size recompute has to move it once it commits."""

    def test_add_moves_the_version(self, rom: Rom):
        before = _filter_values_cache_version()

        _add_rom_file(rom)

        assert _filter_values_cache_version() != before

    def test_delete_moves_the_version(self, rom: Rom):
        game = _add_rom_file(rom)
        before = _filter_values_cache_version()

        db_rom_handler.delete_rom_file(game.id)

        assert _filter_values_cache_version() != before

    def test_resize_moves_the_version(self, rom: Rom):
        game = _add_rom_file(rom)
        before = _filter_values_cache_version()

        db_rom_handler.update_rom_file(game.id, {"file_size_bytes": 5})

        assert _filter_values_cache_version() != before

    def test_rename_leaves_the_version(self, rom: Rom):
        game = _add_rom_file(rom)
        before = _filter_values_cache_version()

        db_rom_handler.update_rom_file(game.id, {"file_name": "renamed.bin"})

        assert _filter_values_cache_version() == before

    def test_unknown_delete_leaves_the_version(self, rom: Rom):
        before = _filter_values_cache_version()

        db_rom_handler.delete_rom_file(999_999)

        assert _filter_values_cache_version() == before

    def test_rolled_back_write_leaves_the_version(self, rom: Rom):
        before = _filter_values_cache_version()

        with pytest.raises(RuntimeError), sync_session.begin() as session:
            _add_rom_file(rom, session=session)
            raise RuntimeError("abort")

        assert _filter_values_cache_version() == before
        assert db_rom_handler.rom_files_for_rom_id(rom.id) == []

    def test_one_transaction_moves_the_version_once(self, rom: Rom):
        before = int(_filter_values_cache_version())

        with sync_session.begin() as session:
            for name in ("a.bin", "b.bin"):
                _add_rom_file(rom, name, size=10, session=session)

        assert int(_filter_values_cache_version()) == before + 1


class TestRomFileSizeLocking:
    """Concurrent writers to one rom serialise on its row, taken before the
    file write so the foreign key check cannot lock it first."""

    @pytest.fixture
    def statements(self) -> Iterator[list[str]]:
        seen: list[str] = []

        def record(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
            seen.append(" ".join(statement.split()))

        event.listen(sync_engine, "before_cursor_execute", record)
        yield seen
        event.remove(sync_engine, "before_cursor_execute", record)

    @staticmethod
    def _first(statements: list[str], prefix: str) -> int:
        return next(i for i, s in enumerate(statements) if s.startswith(prefix))

    def _assert_locked_before(self, statements: list[str], write: str) -> None:
        lock = next(
            i
            for i, s in enumerate(statements)
            if s.startswith("SELECT roms.id") and re.search(r"FOR (NO KEY )?UPDATE$", s)
        )
        assert lock < self._first(statements, write)
        assert self._first(statements, write) < self._first(
            statements, "UPDATE roms SET fs_size_bytes"
        )

    def test_add_locks_the_rom_first(self, rom: Rom, statements: list[str]):
        _add_rom_file(rom)

        self._assert_locked_before(statements, "INSERT INTO rom_files")

    def test_delete_locks_the_rom_first(self, rom: Rom, statements: list[str]):
        game = _add_rom_file(rom)
        statements.clear()

        db_rom_handler.delete_rom_file(game.id)

        self._assert_locked_before(statements, "DELETE FROM rom_files")

    def test_resize_locks_the_rom_first(self, rom: Rom, statements: list[str]):
        game = _add_rom_file(rom)
        statements.clear()

        db_rom_handler.update_rom_file(game.id, {"file_size_bytes": 5})

        self._assert_locked_before(statements, "UPDATE rom_files")

    def test_move_locks_its_roms_before_the_file(
        self, rom: Rom, second_rom: Rom, statements: list[str]
    ):
        # Folder conversion writes the rom row before its file rows, so file
        # writes lock in the same order.
        game = _add_rom_file(rom)
        statements.clear()

        db_rom_handler.update_rom_file(game.id, {"rom_id": second_rom.id})

        file_lock = next(
            i
            for i, s in enumerate(statements)
            if s.startswith("SELECT rom_files.rom_id") and s.endswith("FOR UPDATE")
        )
        rom_locks = [
            i
            for i, s in enumerate(statements)
            if s.startswith("SELECT roms.id") and re.search(r"FOR (NO KEY )?UPDATE$", s)
        ]
        assert len(rom_locks) == 2
        assert max(rom_locks) < file_lock

    def test_an_owner_changed_meanwhile_fails_the_write(self):
        session = MagicMock()
        # The file moved from rom 1 to rom 2 before this transaction locked rom 1.
        session.scalar.side_effect = [1, 2]

        with pytest.raises(RomFileOwnerChangedError):
            db_rom_handler._lock_rom_file_and_roms(10, [3], session)

    def test_a_move_into_a_locked_rom_needs_no_more_locks(self):
        session = MagicMock()
        session.scalar.side_effect = [1, 3]

        locked = db_rom_handler._lock_rom_file_and_roms(10, [3], session)

        assert locked == {1, 3}
        assert session.execute.call_count == 2

    def test_a_vanished_file_locks_nothing_more(self):
        session = MagicMock()
        session.scalar.side_effect = [None]

        assert db_rom_handler._lock_rom_file_and_roms(10, [3], session) is None
        session.execute.assert_not_called()

    @pytest.mark.parametrize(
        ("dialect", "clause"),
        [(MARIADB_DIALECT, "FOR UPDATE"), (POSTGRESQL_DIALECT, "FOR NO KEY UPDATE")],
    )
    def test_lock_spelling(self, dialect: Dialect, clause: str):
        # NO KEY UPDATE leaves other tables' foreign key checks on the row free.
        session = MagicMock()

        db_rom_handler._lock_rom_rows([7], session)

        (statement,) = session.execute.call_args.args
        assert compile_sql(statement, dialect).endswith(clause)

    def test_move_locks_both_roms_in_id_order(self, rom: Rom, second_rom: Rom):
        # Two opposite moves take the locks in the same order, so they cannot
        # deadlock.
        session = MagicMock()

        db_rom_handler._lock_rom_rows([second_rom.id, rom.id, second_rom.id], session)

        locked = [
            call.args[0].compile().params["id_1"]
            for call in session.execute.call_args_list
        ]
        assert locked == sorted({rom.id, second_rom.id})
