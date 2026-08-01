from models.rom import LookupHashes, Rom, RomFile


def test_rom(rom: Rom):
    assert rom.fs_path == "test_platform_slug/roms"
    assert rom.full_path == "test_platform_slug/roms/test_rom.zip"


def test_rom_with_libretro_match_is_identified(rom: Rom):
    rom.libretro_id = "abc123"

    assert rom.is_unidentified is False
    assert rom.is_identified is True


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
    file = RomFile(
        file_name="sf2.zip",
        file_path="arcade",
        file_size_bytes=100,
        crc_hash="compositecrc",
        md5_hash="compositemd5",
        sha1_hash="compositesha1",
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
