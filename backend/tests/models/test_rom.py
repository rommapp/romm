from typing import Any

import pytest
from tests.factories import make_rom

from handler.database import db_rom_handler
from handler.database.base_handler import sync_session
from models.platform import Platform
from models.rom import (
    SEARCH_TEXT_MAX_LENGTH,
    LookupHashes,
    Rom,
    RomFile,
    compute_full_path_hash,
    compute_search_titles,
)


def test_rom(rom: Rom):
    assert rom.fs_path == "test_platform_slug/roms"
    assert rom.full_path == "test_platform_slug/roms/test_rom.zip"


def test_rom_defaults_to_non_physical(rom: Rom):
    assert rom.is_physical is False
    assert rom.upc is None


def test_physical_rom_round_trips(platform: Platform):
    rom = make_rom(
        platform,
        "Sonic the Hedgehog",
        fs_extension="",
        fs_path=f"{platform.slug}/roms/.physical",
        fs_size_bytes=0,
        is_physical=True,
        upc="012345678905",
    )

    stored = db_rom_handler.get_rom(rom.id)
    assert stored is not None
    assert stored.is_physical is True
    assert stored.upc == "012345678905"


def test_has_file_on_disk_covers_both_file_less_cases(rom: Rom):
    assert rom.has_file_on_disk is True

    rom.missing_from_fs = True
    assert rom.has_file_on_disk is False

    rom.missing_from_fs = False
    rom.is_physical = True
    assert rom.has_file_on_disk is False


def test_rom_with_libretro_match_is_identified(rom: Rom):
    rom.libretro_id = "abc123"

    assert rom.is_unidentified is False
    assert rom.is_identified is True


@pytest.mark.parametrize(
    "fs_path, fs_name, file_path, file_name, expected",
    [
        ("roms/ps2", "gta.iso", "roms/ps2", "gta.iso", True),
        ("roms/ps2/Action", "gta.iso", "roms/ps2/Action", "gta.iso", True),
        ("ps2", "gta.iso", "ps2", "gta.iso", True),
        ("roms/ps2", "FF X", "roms/ps2/FF X", "disc1.iso", True),
        ("ps2", "FF X", "ps2/FF X", "disc1.iso", True),
        ("roms/ps2/RPG", "FF X", "roms/ps2/RPG/FF X", "disc1.iso", True),
        ("roms/ps2", "FF X", "roms/ps2/FF X/dlc", "extra.bin", False),
        ("ps2", "FF X", "ps2/FF X/dlc", "extra.bin", False),
    ],
)
def test_is_top_level_at_any_folder_depth(
    fs_path: str, fs_name: str, file_path: str, file_name: str, expected: bool
):
    rom = Rom(fs_path=fs_path, fs_name=fs_name)
    file = RomFile(rom=rom, file_path=file_path, file_name=file_name)

    assert file.is_top_level is expected


def _archive(**kwargs) -> RomFile:
    return RomFile(
        file_name="sf2.zip",
        file_path="arcade",
        file_size_bytes=100,
        crc_hash="compositecrc",
        md5_hash="compositemd5",
        sha1_hash="compositesha1",
        **kwargs,
    )


def test_lookup_hashes_uses_the_files_own_digests_by_default():
    file = RomFile(
        file_name="game.nes",
        file_path="nes",
        file_size_bytes=100,
        crc_hash="crc",
        md5_hash="md5",
        sha1_hash="sha1",
    )

    assert file.lookup_hashes == LookupHashes(crc="crc", md5="md5", sha1="sha1")


def test_lookup_hashes_prefers_the_chd_disc_data_sha1():
    """A CHD's own digests cover the container, so only the embedded SHA1 is
    worth sending."""
    file = RomFile(
        file_name="game.chd",
        file_path="dc",
        file_size_bytes=100,
        crc_hash="containercrc",
        md5_hash="containermd5",
        sha1_hash="containersha1",
        chd_sha1_hash="discsha1",
    )

    assert file.lookup_hashes == LookupHashes(crc=None, md5=None, sha1="discsha1")


def test_lookup_hashes_picks_the_largest_archive_member():
    """ROM databases index a multi-file archive by the ROM inside it, not by
    the composite hash RomM stores for the archive as a whole."""
    file = _archive(
        archive_members=[
            {
                "name": "readme.txt",
                "size": 10,
                "crc_hash": "readmecrc",
                "md5_hash": "readmemd5",
                "sha1_hash": "readmesha1",
            },
            {
                "name": "sf2.rom",
                "size": 2048,
                "crc_hash": "romcrc",
                "md5_hash": "rommd5",
                "sha1_hash": "romsha1",
            },
        ],
    )

    assert file.lookup_hashes == LookupHashes(
        crc="romcrc", md5="rommd5", sha1="romsha1"
    )


def test_lookup_hashes_of_a_single_member_archive_are_the_files_own():
    """The composite of a one-member archive is that member's digest, so this
    case must keep sending exactly what it sent before."""
    file = _archive(
        archive_members=[
            {
                "name": "sf2.rom",
                "size": 2048,
                "crc_hash": "compositecrc",
                "md5_hash": "compositemd5",
                "sha1_hash": "compositesha1",
            },
        ],
    )

    assert file.lookup_hashes == LookupHashes(
        crc="compositecrc", md5="compositemd5", sha1="compositesha1"
    )


def test_lookup_hashes_without_archive_members_uses_the_files_own_digests():
    """Rows scanned before 4.9.0, unreadable archives hashed as raw bytes, and
    archives nested inside a folder ROM all leave `archive_members` NULL, and
    their own hash is already the largest member's."""
    file = _archive(archive_members=None)

    assert file.lookup_hashes == LookupHashes(
        crc="compositecrc", md5="compositemd5", sha1="compositesha1"
    )


def test_lookup_hashes_with_empty_archive_members_uses_the_files_own_digests():
    file = _archive(archive_members=[])

    assert file.lookup_hashes == LookupHashes(
        crc="compositecrc", md5="compositemd5", sha1="compositesha1"
    )


def test_lookup_hashes_tolerates_a_member_without_a_size():
    file = _archive(
        archive_members=[
            {
                "name": "unsized.bin",
                "crc_hash": "unsizedcrc",
                "md5_hash": "unsizedmd5",
                "sha1_hash": "unsizedsha1",
            },
            {
                "name": "nosize.bin",
                "size": None,
                "crc_hash": "nosizecrc",
                "md5_hash": "nosizemd5",
                "sha1_hash": "nosizesha1",
            },
            {
                "name": "sf2.rom",
                "size": 2048,
                "crc_hash": "romcrc",
                "md5_hash": "rommd5",
                "sha1_hash": "romsha1",
            },
        ],
    )

    assert file.lookup_hashes == LookupHashes(
        crc="romcrc", md5="rommd5", sha1="romsha1"
    )


@pytest.mark.parametrize(
    "stored",
    [
        "javascript:x",
        "../../evil",
        "ugPZnsRH٣k٣",
        "short",
        "waytoolongvideoid",
        None,
        12345,
    ],
)
def test_youtube_video_id_drops_anything_that_is_not_an_id(rom: Rom, stored):
    """raw_*_metadata is client-writable, so the embed must not trust the blob."""
    rom.igdb_metadata = {"youtube_video_id": stored}

    assert rom.youtube_video_id is None


def test_youtube_video_id_falls_through_to_the_next_valid_source(rom: Rom):
    rom.igdb_metadata = {"youtube_video_id": "javascript:x"}
    rom.demozoo_metadata = {"youtube_video_id": "ugPZnsRHUkc"}

    assert rom.youtube_video_id == "ugPZnsRHUkc"


class TestFullPathHash:
    """The digest the unique index reads, since fs_path plus fs_name is 5804
    bytes of utf8mb4 and InnoDB caps a key at 3072."""

    def test_it_digests_the_full_path_whichever_half_is_assigned_first(self):
        expected = compute_full_path_hash("nes/roms/Hacks", "Game.zip")

        name_first = Rom(fs_name="Game.zip", fs_path="nes/roms/Hacks")
        path_first = Rom(fs_path="nes/roms/Hacks", fs_name="Game.zip")

        assert name_first.full_path_hash == expected
        assert path_first.full_path_hash == expected

    def test_it_is_re_derived_when_either_half_changes(self, rom: Rom):
        rom.fs_path = "test_platform_slug/roms/Hacks"
        assert rom.full_path_hash == compute_full_path_hash(
            "test_platform_slug/roms/Hacks", "test_rom.zip"
        )

        rom.fs_name = "renamed.zip"
        assert rom.full_path_hash == compute_full_path_hash(
            "test_platform_slug/roms/Hacks", "renamed.zip"
        )

    def test_the_cached_full_path_does_not_survive_a_rename(self, rom: Rom):
        """A scan reads `full_path` and then renames the file in place, so the
        cached pair has to be dropped when either half is set."""
        assert rom.full_path == "test_platform_slug/roms/test_rom.zip"

        rom.fs_name = "renamed.zip"
        assert rom.full_path == "test_platform_slug/roms/renamed.zip"

        rom.fs_path = "test_platform_slug/roms/Hacks"
        assert rom.full_path == "test_platform_slug/roms/Hacks/renamed.zip"

    def test_the_same_name_in_two_folders_is_two_distinct_roms(self):
        """What the (platform_id, fs_name) index used to forbid, and what a
        custom library structure makes ordinary."""
        root = Rom(fs_name="Game.zip", fs_path="nes/roms")
        nested = Rom(fs_name="Game.zip", fs_path="nes/roms/Hacks")

        assert root.full_path_hash != nested.full_path_hash


def _achievement(ra_id: int | None, display_order: int | None) -> dict[str, Any]:
    return {
        "ra_id": ra_id,
        "display_order": display_order,
        "badge_path": f"{ra_id}.png",
        "badge_path_lock": f"{ra_id}_lock.png",
    }


class TestMergedRAMetadata:
    def test_achievements_come_back_in_retroachievements_display_order(self):
        rom = Rom(
            fs_name="Game.zip",
            fs_path="nes/roms",
            ra_metadata={
                "achievements": [
                    _achievement(30, 3),
                    _achievement(10, 1),
                    _achievement(20, 2),
                ]
            },
        )

        merged = rom.merged_ra_metadata
        assert merged is not None
        assert [a["ra_id"] for a in merged["achievements"]] == [10, 20, 30]

    def test_ties_and_missing_orders_stay_deterministic(self):
        rom = Rom(
            fs_name="Game.zip",
            fs_path="nes/roms",
            ra_metadata={
                "achievements": [
                    _achievement(None, None),
                    _achievement(9, None),
                    _achievement(8, 1),
                    _achievement(7, 1),
                ]
            },
        )

        merged = rom.merged_ra_metadata
        assert merged is not None
        assert [a["ra_id"] for a in merged["achievements"]] == [7, 8, 9, None]

    def test_the_stored_metadata_keeps_its_own_order_and_relative_paths(self):
        """Badge paths on disk stay relative for the filesystem handlers."""
        stored = {"achievements": [_achievement(2, 2), _achievement(1, 1)]}
        rom = Rom(fs_name="Game.zip", fs_path="nes/roms", ra_metadata=stored)

        merged = rom.merged_ra_metadata

        assert merged is not None
        assert [a["ra_id"] for a in stored["achievements"]] == [2, 1]
        assert stored["achievements"][0]["badge_path"] == "2.png"


def test_search_titles_fold_the_name_then_each_alias():
    titles = compute_search_titles(
        "Final  Fantasy\tVII",
        {
            "igdb_metadata": {"alternative_names": ["FF7", "ŌKAMI Den", "ff7", ""]},
            "moby_metadata": {"alternate_titles": ["Final Fantasy 7"]},
            "ss_metadata": {"alternative_names": ["FINAL FANTASY VII"]},
        },
    )

    assert titles == "\x1ffinal fantasy vii\x1fff7\x1fōkami den\x1ffinal fantasy 7\x1f"


def test_search_titles_skip_a_hand_edited_blob_that_is_not_an_object():
    titles = compute_search_titles(
        "Name", {"igdb_metadata": ["FF7"], "moby_metadata": "FF7"}
    )

    assert titles == "\x1fname\x1f"


def test_search_titles_keep_the_name_slot_without_a_name_or_metadata():
    assert compute_search_titles(None, {"igdb_metadata": None}) == "\x1f\x1f"


def test_search_titles_drop_aliases_past_the_length_cap():
    aliases = [f"alias {i:05d} " + "x" * 100 for i in range(500)]

    titles = compute_search_titles(
        "Name", {"igdb_metadata": {"alternative_names": aliases}}
    )

    assert len(titles) <= SEARCH_TEXT_MAX_LENGTH
    assert titles.endswith("\x1f")


def test_search_titles_keep_a_short_alias_after_one_past_the_cap():
    titles = compute_search_titles(
        "Name",
        {"igdb_metadata": {"alternative_names": ["x" * SEARCH_TEXT_MAX_LENGTH, "FF7"]}},
    )

    assert titles == "\x1fname\x1fff7\x1f"


def test_search_titles_take_the_hand_set_titles_over_the_providers():
    titles = compute_search_titles(
        "Name",
        {
            "igdb_metadata": {"alternative_names": ["FF7"]},
            "manual_metadata": {"alternative_names": ["FFVII"]},
        },
    )

    assert titles == "\x1fname\x1fffvii\x1f"


def test_search_titles_fall_back_to_the_providers_when_the_hand_set_list_is_empty():
    titles = compute_search_titles(
        "Name",
        {
            "igdb_metadata": {"alternative_names": ["FF7"]},
            "manual_metadata": {"alternative_names": []},
        },
    )

    assert titles == "\x1fname\x1fff7\x1f"


def test_search_titles_follow_orm_and_bulk_writes(platform: Platform):
    rom = make_rom(
        platform, "Final Fantasy VII", igdb_metadata={"alternative_names": ["FF7"]}
    )

    def stored() -> str | None:
        with sync_session.begin() as session:
            return session.get_one(Rom, rom.id).search_titles

    assert stored() == "\x1ffinal fantasy vii\x1fff7\x1f"

    db_rom_handler.update_rom(rom.id, {"name": "Final Fantasy VII (PAL)"})
    assert stored() == "\x1ffinal fantasy vii (pal)\x1fff7\x1f"

    db_rom_handler.update_rom(
        rom.id, {"moby_metadata": {"alternate_titles": ["FFVII"]}}
    )
    assert stored() == "\x1ffinal fantasy vii (pal)\x1fff7\x1fffvii\x1f"

    with sync_session.begin() as session:
        session.get_one(Rom, rom.id).name = "Final Fantasy VII International"
    assert stored() == "\x1ffinal fantasy vii international\x1fff7\x1fffvii\x1f"


def test_alternative_names_join_every_providers_titles():
    rom = Rom(
        name="Final Fantasy VII",
        igdb_metadata={"alternative_names": ["FF7"]},
        moby_metadata={"alternate_titles": ["FF7", "Final Fantasy 7"]},
        ss_metadata={"alternative_names": ["FFVII"]},
    )

    assert rom.alternative_names == ["FF7", "Final Fantasy 7", "FFVII"]


def test_alternative_names_keep_one_of_each_title_however_it_is_spaced():
    rom = Rom(
        name="3D Baseball",
        igdb_metadata={"alternative_names": ["3D Baseball: The Majors"]},
        ss_metadata={
            "alternative_names": [
                "3D Baseball: The Majors ",
                "3D BASEBALL: THE MAJORS",
                " ",
            ]
        },
    )

    assert rom.alternative_names == ["3D Baseball: The Majors"]


def test_alternative_names_take_the_hand_set_titles_over_the_providers():
    rom = Rom(
        name="Final Fantasy VII",
        igdb_metadata={"alternative_names": ["FF7"]},
        manual_metadata={"alternative_names": ["Final Fantasy Seven"]},
    )

    assert rom.alternative_names == ["Final Fantasy Seven"]


def test_alternative_names_leave_out_the_displayed_name():
    rom = Rom(
        name="ファイナルファンタジーVII",
        igdb_metadata={
            "alternative_names": ["Final Fantasy VII", "ファイナルファンタジーVII"]
        },
    )

    assert rom.alternative_names == ["Final Fantasy VII"]


def test_alternative_names_skip_a_hand_edited_blob_that_is_not_a_list():
    rom = Rom(
        name="Final Fantasy VII",
        igdb_metadata={"alternative_names": "FF7"},
        manual_metadata={"alternative_names": ["Final Fantasy Seven", 7]},
    )

    assert rom.alternative_names == ["Final Fantasy Seven"]
