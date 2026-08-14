"""Searching the gallery by a hash digest.

The search box offers "name, filename, hash", but the term only ever reached
`roms.name` / `roms.fs_name`. A term shaped like a CRC32, MD5/RA or SHA-1
digest now also matches the hash columns on `roms` and `rom_files`, without
taking anything away from the name search.
"""

import pytest
from sqlalchemy.orm import Query

from handler.database import db_collection_handler, db_rom_handler
from models.collection import SmartCollection
from models.platform import Platform
from models.rom import Rom, RomFile
from models.user import User

AERO_CRC = "95b07885"
AERO_MD5 = "c5347ceb9cfdabb188d3a1bf5f3a7f94"
AERO_SHA1 = "ddacbb35c87232d701240717aa1ed43ab7f4c253"
AERO_RA = "1f0b3d7a4c9e2b8d6a5f0c3e7b1d9a4c"

DISC_ONE_MD5 = "0bd9d1d0a2f6e4c8b7a5931e0f2c4d68"
DISC_TWO_CRC = "1a2b3c4d"
DISC_CHD_SHA1 = "aaaaaaaabbbbbbbbccccccccddddddddeeeeeeee"
SHARED_TRACK_CRC = "beefcafe"


def _add_rom(platform: Platform, name: str, **hashes: str) -> Rom:
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
            **hashes,
        )
    )


def _add_files(rom: Rom, files: list[RomFile]) -> None:
    db_rom_handler.sync_rom_files(rom.id, files)


def _file(rom: Rom, file_name: str, **hashes: str) -> RomFile:
    return RomFile(
        rom_id=rom.id,
        file_name=file_name,
        file_path=rom.fs_path,
        file_size_bytes=100,
        **hashes,
    )


def _search_ids(term: str) -> list[int]:
    return [r.id for r in db_rom_handler.get_roms_scalar(search_term=term)]


def _search_sql(term: str) -> str:
    query = db_rom_handler._filter_by_search_term(Query(Rom.id), term)
    return str(query.statement.compile(compile_kwargs={"literal_binds": True}))


@pytest.fixture
def aero(platform: Platform) -> Rom:
    """A single-file ROM carrying every hash on the `roms` row itself."""
    return _add_rom(
        platform,
        "Aero Fighters",
        crc_hash=AERO_CRC,
        md5_hash=AERO_MD5,
        sha1_hash=AERO_SHA1,
        ra_hash=AERO_RA,
    )


@pytest.fixture
def multi_disc(platform: Platform) -> Rom:
    """A multi-disc ROM whose hashes live on its files, not on the ROM."""
    rom = _add_rom(platform, "Chrono Cross")
    _add_files(
        rom,
        [
            _file(rom, "disc1.chd", md5_hash=DISC_ONE_MD5, chd_sha1_hash=DISC_CHD_SHA1),
            _file(rom, "disc2.chd", crc_hash=DISC_TWO_CRC),
        ],
    )
    return rom


class TestRomHashSearch:
    @pytest.mark.parametrize(
        "term",
        [AERO_CRC, AERO_MD5, AERO_SHA1, AERO_RA],
        ids=["crc", "md5", "sha1", "ra"],
    )
    def test_each_rom_hash_finds_the_rom(self, aero: Rom, term: str):
        assert _search_ids(term) == [aero.id]

    def test_hash_search_is_case_insensitive(self, aero: Rom):
        assert _search_ids(AERO_MD5.upper()) == [aero.id]

    def test_hash_of_another_rom_is_not_matched(self, aero: Rom, platform: Platform):
        other = _add_rom(platform, "Gunstar Heroes", md5_hash=DISC_ONE_MD5)

        assert _search_ids(AERO_MD5) == [aero.id]
        assert _search_ids(DISC_ONE_MD5) == [other.id]

    def test_partial_hash_prefix_finds_nothing(self, aero: Rom):
        assert _search_ids(AERO_MD5[:16]) == []
        assert _search_ids(AERO_CRC[:7]) == []


class TestRomFileHashSearch:
    """For multi-file games the hash a user has in hand is a file's, not the
    game's, so the file rows have to be searched too."""

    def test_file_md5_returns_the_owning_rom(self, multi_disc: Rom):
        assert _search_ids(DISC_ONE_MD5) == [multi_disc.id]

    def test_file_crc_returns_the_owning_rom(self, multi_disc: Rom):
        assert _search_ids(DISC_TWO_CRC) == [multi_disc.id]

    def test_chd_data_sha1_returns_the_owning_rom(self, multi_disc: Rom):
        assert _search_ids(DISC_CHD_SHA1) == [multi_disc.id]

    def test_rom_matching_on_several_files_is_returned_once(self, platform: Platform):
        """Identical tracks share a hash; the ROM must not come back twice."""
        rom = _add_rom(platform, "Policenauts")
        _add_files(
            rom,
            [
                _file(rom, "track02.bin", crc_hash=SHARED_TRACK_CRC),
                _file(rom, "track03.bin", crc_hash=SHARED_TRACK_CRC),
            ],
        )

        assert _search_ids(SHARED_TRACK_CRC) == [rom.id]

    def test_rom_and_file_hash_match_returns_it_once(self, platform: Platform):
        rom = _add_rom(platform, "Einhander", md5_hash=DISC_ONE_MD5)
        _add_files(rom, [_file(rom, "einhander.bin", md5_hash=DISC_ONE_MD5)])

        assert _search_ids(DISC_ONE_MD5) == [rom.id]


class TestNameSearchIsNotDegraded:
    """Hash conditions are added to the name conditions, never swapped in for
    them, so a term that happens to look like a digest still searches names."""

    def test_hash_shaped_term_still_matches_names(self, platform: Platform):
        named = _add_rom(platform, "deadbeef")
        hashed = _add_rom(platform, "Some Other Game", crc_hash="deadbeef")

        assert set(_search_ids("deadbeef")) == {named.id, hashed.id}

    def test_plain_name_search_is_unchanged(self, aero: Rom, platform: Platform):
        _add_rom(platform, "Super Mario World")

        assert _search_ids("Aero Fighters") == [aero.id]
        assert _search_ids("aerofgt") == []

    def test_filename_search_is_unchanged(self, aero: Rom):
        assert _search_ids("Aero_Fighters.zip") == [aero.id]

    def test_hash_term_combines_with_name_terms(self, aero: Rom, platform: Platform):
        mario = _add_rom(platform, "Super Mario World")

        assert set(_search_ids(f"Super Mario|{AERO_MD5}")) == {mario.id, aero.id}

    def test_non_digest_length_hex_term_is_a_name_search_only(self, platform: Platform):
        """16 hex chars is not a digest length, so it must not reach the hash
        columns, and a name containing it still matches."""
        named = _add_rom(platform, "abcdef0123456789 Edition")
        _add_rom(platform, "Unrelated", md5_hash=AERO_MD5)

        assert _search_ids("abcdef0123456789") == [named.id]


class TestSmartCollectionSearchTerm:
    """A smart collection's "search term" criterion runs through the same
    filter, so one built on a hash used to always be empty."""

    def _smart_collection(self, user: User, term: str) -> SmartCollection:
        return db_collection_handler.add_smart_collection(
            SmartCollection(
                name=f"Hash {term}",
                description="",
                user_id=user.id,
                filter_criteria={"search_term": term},
            )
        )

    def test_hash_criterion_resolves_members(self, aero: Rom, admin_user: User):
        collection = self._smart_collection(admin_user, AERO_MD5)

        roms = db_rom_handler.get_roms_scalar(
            smart_collection_id=collection.id, user_id=admin_user.id
        )

        assert [rom.id for rom in roms] == [aero.id]

    def test_file_hash_criterion_resolves_members(
        self, multi_disc: Rom, admin_user: User
    ):
        collection = self._smart_collection(admin_user, DISC_ONE_MD5)

        roms = db_rom_handler.get_roms_scalar(
            smart_collection_id=collection.id, user_id=admin_user.id
        )

        assert [rom.id for rom in roms] == [multi_disc.id]


class TestSearchQueryShape:
    """The two sides are unioned rather than OR'd. OR-ing them costs the
    name side its index (no engine merges a full-text index with a B-tree
    one), turning every hash search into a full scan of `roms`."""

    def test_name_search_builds_no_hash_sql(self):
        sql = _search_sql("Aero Fighters")

        assert "hash" not in sql
        assert "UNION" not in sql.upper()

    def test_hash_search_unions_the_two_sides(self):
        sql = _search_sql(AERO_MD5)

        assert "UNION" in sql.upper()
        assert "roms.md5_hash" in sql
        assert "rom_files.md5_hash" in sql
        # The name side must reach the union on its own, never OR'd onto a hash.
        assert "MATCH" not in sql.split("UNION")[1].upper()

    def test_hash_search_queries_only_the_matching_digest_length(self):
        sql = _search_sql(AERO_CRC)

        assert "crc_hash" in sql
        assert "md5_hash" not in sql
        assert "sha1_hash" not in sql
