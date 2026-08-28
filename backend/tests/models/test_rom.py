from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import LookupHashes, Rom, RomFile


def test_rom(rom: Rom):
    assert rom.fs_path == "test_platform_slug/roms"
    assert rom.full_path == "test_platform_slug/roms/test_rom.zip"


def test_rom_defaults_to_non_physical(rom: Rom):
    assert rom.is_physical is False
    assert rom.upc is None


def test_physical_rom_round_trips(platform: Platform):
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="Sonic the Hedgehog",
            fs_name="Sonic the Hedgehog",
            fs_path=f"{platform.slug}/roms/.physical",
            fs_size_bytes=0,
            is_physical=True,
            upc="012345678905",
        )
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
