"""Ordering the gallery by a `roms_metadata` field.

`roms_metadata` is a thin view over STORED generated columns on `roms`
(migration 0098). Resolving one of its columns as the sort key used to join the
view back in, which re-joins `roms` to itself and leaves the sort key on the
joined table: the database cannot read that from an index, so it filesorts the
whole library on every page. The generated columns are indexed on `roms`, so
these tests pin both the ordering results and the query reading them directly.
"""

import pytest

from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _make_rom(platform: Platform, fs_name: str, **metadata) -> Rom:
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=fs_name,
            slug=fs_name,
            fs_name=f"{fs_name}.zip",
            fs_name_no_tags=fs_name,
            fs_name_no_ext=fs_name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    if metadata:
        rom = db_rom_handler.update_rom(rom.id, metadata)
    return rom


def _ordered_names(**kwargs) -> list[str]:
    return [rom.name for rom in db_rom_handler.get_roms_scalar(**kwargs)]


class TestMetadataSortQueryShape:
    """The sort key has to be a `roms` column for its index to be usable."""

    @pytest.mark.parametrize(
        ("order_by", "expected_column"),
        [
            ("first_release_date", "generated_first_release_date"),
            ("average_rating", "generated_average_rating"),
            ("player_count", "generated_player_count"),
        ],
    )
    def test_orders_by_the_indexed_roms_column(
        self, order_by: str, expected_column: str
    ):
        query, order_column = db_rom_handler.get_roms_query(order_by=order_by)
        sql = str(query)

        assert f"ORDER BY roms.{expected_column} ASC" in sql
        assert order_column is getattr(Rom, expected_column)
        # `Rom.metadatum` is a `lazy="joined"` eager load, so one join to the
        # view is expected; the sort must not add a second one.
        assert sql.count("JOIN roms_metadata") == 1

    def test_descending_metadata_sort_keeps_the_roms_column(self):
        query, _ = db_rom_handler.get_roms_query(
            order_by="first_release_date", order_dir="desc"
        )

        assert "ORDER BY roms.generated_first_release_date DESC" in str(query)

    def test_rom_column_sort_is_unchanged(self):
        query, order_column = db_rom_handler.get_roms_query(order_by="fs_size_bytes")

        assert "ORDER BY roms.fs_size_bytes ASC" in str(query)
        assert order_column is Rom.fs_size_bytes

    def test_metadata_sort_does_not_join_the_view_for_a_user(
        self, admin_user: User, platform: Platform
    ):
        query, _ = db_rom_handler.get_roms_query(
            order_by="first_release_date", user_id=admin_user.id
        )
        sql = str(query)

        # The rom_user join still has to be there, only the self-join goes.
        assert sql.count("JOIN roms_metadata") == 1
        assert "JOIN rom_user" in sql


class TestMetadataSortResults:
    """The values sorted on are the ones the view exposes."""

    @pytest.fixture
    def dated_roms(self, platform: Platform) -> None:
        _make_rom(
            platform, "middle", igdb_metadata={"first_release_date": "1000000000"}
        )
        _make_rom(platform, "oldest", igdb_metadata={"first_release_date": "100000000"})
        _make_rom(
            platform, "newest", igdb_metadata={"first_release_date": "1700000000"}
        )

    def test_first_release_date_ascending(self, dated_roms: None):
        assert _ordered_names(order_by="first_release_date", order_dir="asc") == [
            "oldest",
            "middle",
            "newest",
        ]

    def test_average_rating_descending(self, platform: Platform):
        _make_rom(platform, "mediocre", igdb_metadata={"total_rating": "50"})
        _make_rom(platform, "great", igdb_metadata={"total_rating": "95"})
        _make_rom(platform, "poor", igdb_metadata={"total_rating": "10"})

        assert _ordered_names(order_by="average_rating", order_dir="desc") == [
            "great",
            "mediocre",
            "poor",
        ]

    def test_player_count_ascending(self, platform: Platform):
        _make_rom(platform, "four", igdb_metadata={"player_count": "4"})
        _make_rom(platform, "two", igdb_metadata={"player_count": "2"})

        assert _ordered_names(order_by="player_count", order_dir="asc") == [
            "two",
            "four",
        ]

    def test_roms_without_metadata_are_still_returned(self, platform: Platform):
        """An unmatched rom has no release date, and must not be filtered out."""
        _make_rom(platform, "dated", igdb_metadata={"first_release_date": "100000000"})
        _make_rom(platform, "undated")

        names = _ordered_names(order_by="first_release_date", order_dir="asc")

        # NULL ordering differs per engine, so only membership is asserted.
        assert sorted(names) == ["dated", "undated"]

    def test_sort_matches_the_values_the_view_exposes(self, platform: Platform):
        rom = _make_rom(
            platform, "quoted", igdb_metadata={"first_release_date": "1569369600"}
        )

        reloaded = db_rom_handler.get_rom(rom.id)
        assert reloaded is not None
        assert reloaded.metadatum.first_release_date == 1569369600000
        assert reloaded.generated_first_release_date == 1569369600000
