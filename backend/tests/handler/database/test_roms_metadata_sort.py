"""Ordering the gallery by a `roms_metadata` field.

`roms_metadata` is a thin view over STORED generated columns on `roms`
(migration 0098). Resolving one of its columns as the sort key used to join the
view back in, which re-joins `roms` to itself and leaves the sort key on the
joined table: the database cannot read that from an index, so it filesorts the
whole library on every page. The generated columns are indexed on `roms`, so
these tests pin both the ordering results and the query reading them directly.

NULL sort keys (unmatched roms) land last on every engine and both directions.
Descending stays on the index (MariaDB/MySQL place NULLs last on DESC natively,
PostgreSQL gets an explicit NULLS LAST); ascending on MariaDB/MySQL takes a
leading IS NULL term and gives up the index order.
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
    def test_orders_by_the_roms_column_with_nulls_last(
        self, monkeypatch: pytest.MonkeyPatch, order_by: str, expected_column: str
    ):
        monkeypatch.setattr("handler.database.roms_handler.ROMM_DB_DRIVER", "mariadb")
        query, order_column = db_rom_handler.get_roms_query(order_by=order_by)
        sql = str(query)

        assert (
            f"ORDER BY roms.{expected_column} IS NULL, roms.{expected_column} ASC"
        ) in sql
        assert order_column is getattr(Rom, expected_column)
        # `Rom.metadatum` is a `lazy="joined"` eager load, so one join to the
        # view is expected; the sort must not add a second one.
        assert sql.count("JOIN roms_metadata") == 1

    def test_descending_metadata_sort_stays_on_the_index(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("handler.database.roms_handler.ROMM_DB_DRIVER", "mariadb")
        query, _ = db_rom_handler.get_roms_query(
            order_by="first_release_date", order_dir="desc"
        )
        order_sql = str(query).split("ORDER BY")[-1]

        # MariaDB/MySQL place NULLs last on DESC natively; without a leading
        # IS NULL term the sort keeps reading the column's index.
        assert order_sql.strip().startswith("roms.generated_first_release_date DESC")
        assert "IS NULL" not in order_sql

    @pytest.mark.parametrize("order_dir", ["asc", "desc"])
    def test_postgres_sorts_with_native_nulls_last(
        self, monkeypatch: pytest.MonkeyPatch, order_dir: str
    ):
        monkeypatch.setattr(
            "handler.database.roms_handler.ROMM_DB_DRIVER", "postgresql"
        )
        query, _ = db_rom_handler.get_roms_query(
            order_by="first_release_date", order_dir=order_dir
        )
        order_sql = str(query).split("ORDER BY")[-1]

        assert (
            f"roms.generated_first_release_date {order_dir.upper()} NULLS LAST"
            in order_sql
        )
        assert "IS NULL" not in order_sql

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

    @pytest.mark.parametrize("order_dir", ["asc", "desc"])
    def test_roms_without_metadata_stay_in_the_result_and_sort_last(
        self, platform: Platform, order_dir: str
    ):
        """An unmatched rom has no release date; it must not be filtered out,
        and it trails the dated roms in both directions on every engine."""
        _make_rom(platform, "dated", igdb_metadata={"first_release_date": "100000000"})
        _make_rom(platform, "undated")

        names = _ordered_names(order_by="first_release_date", order_dir=order_dir)

        assert names == ["dated", "undated"]

    def test_null_bucket_ties_break_on_the_rom_id(self, platform: Platform):
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
