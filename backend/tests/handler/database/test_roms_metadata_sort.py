"""Ordering the gallery by a `roms_metadata` field.

`roms_metadata` is a thin view over STORED generated columns on `roms`
(migration 0098). Resolving one of its columns as the sort key used to join the
view back in, which re-joins `roms` to itself and leaves the sort key on the
joined table: the database cannot read that from an index, so it filesorts the
whole library on every page. The generated columns are indexed on `roms`, so
these tests pin both the ordering results and the query reading them directly.

NULL sort keys (unmatched roms) land last on every engine and both directions;
on MariaDB/MySQL the ascending sort pays a leading IS NULL term for it.
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
            ("hltb_main_story", "generated_hltb_main_story"),
        ],
    )
    def test_orders_by_the_roms_column_with_nulls_last(
        self, mariadb_driver: None, order_by: str, expected_column: str
    ):
        query, sort_key = db_rom_handler.get_roms_query(order_by=order_by)
        sql = str(query)

        assert (
            f"ORDER BY roms.{expected_column} IS NULL, roms.{expected_column} ASC"
        ) in sql
        assert sort_key.column is getattr(Rom, expected_column)
        # `Rom.metadatum` is a `lazy="joined"` eager load, so one join to the
        # view is expected; the sort must not add a second one.
        assert sql.count("JOIN roms_metadata") == 1

    # One dialect matrix for the shared NULL-placement block; the rom_user
    # family proves its branch separately through the NULLIF shape test.
    @pytest.mark.parametrize(
        ("driver", "order_dir", "expected"),
        [
            (
                "mariadb",
                "asc",
                "roms.generated_first_release_date IS NULL, "
                "roms.generated_first_release_date ASC",
            ),
            ("mariadb", "desc", "roms.generated_first_release_date DESC"),
            ("postgres", "asc", "roms.generated_first_release_date ASC NULLS LAST"),
            ("postgres", "desc", "roms.generated_first_release_date DESC NULLS LAST"),
        ],
    )
    def test_null_placement_per_dialect(
        self,
        request: pytest.FixtureRequest,
        driver: str,
        order_dir: str,
        expected: str,
    ):
        request.getfixturevalue(f"{driver}_driver")
        query, _ = db_rom_handler.get_roms_query(
            order_by="first_release_date", order_dir=order_dir
        )
        order_sql = str(query).split("ORDER BY")[-1]

        assert order_sql.strip().startswith(expected)
        # The emulation term appears only where the engine needs it.
        emulated = driver == "mariadb" and order_dir == "asc"
        assert ("IS NULL" in order_sql) == emulated

    def test_rom_column_sort_is_unchanged(self):
        query, sort_key = db_rom_handler.get_roms_query(order_by="fs_size_bytes")

        assert "ORDER BY roms.fs_size_bytes ASC" in str(query)
        assert sort_key.column is Rom.fs_size_bytes

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

    def test_grouped_metadata_sort_keeps_the_representative_key(self):
        query, _ = db_rom_handler.get_roms_query(order_by="first_release_date")
        grouped = db_rom_handler.filter_roms(
            query=query, order_by="first_release_date", group_by_meta_id=True
        )
        sql = str(grouped)

        # Roms-side keys stay on the representative: aggregating one would
        # push the dedup window off its covering index.
        assert "group_sort_value" not in sql
        assert "ORDER BY roms.generated_first_release_date ASC" in sql


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

    def test_null_bucket_ties_break_on_the_rom_id(self, platform: Platform):
        """Unmatched roms stay in the result, trail the dated ones in both
        directions, and tie inside the bucket on the rom id."""
        _make_rom(platform, "undated_first")
        _make_rom(platform, "undated_second")
        _make_rom(platform, "dated", igdb_metadata={"first_release_date": "100000000"})

        assert _ordered_names(order_by="first_release_date", order_dir="asc") == [
            "dated",
            "undated_first",
            "undated_second",
        ]
        assert _ordered_names(order_by="first_release_date", order_dir="desc") == [
            "dated",
            "undated_second",
            "undated_first",
        ]

    def test_sort_matches_the_values_the_view_exposes(self, platform: Platform):
        rom = _make_rom(
            platform, "quoted", igdb_metadata={"first_release_date": "1569369600"}
        )

        reloaded = db_rom_handler.get_rom(rom.id)
        assert reloaded is not None
        assert reloaded.metadatum.first_release_date == 1569369600000
        assert reloaded.generated_first_release_date == 1569369600000
