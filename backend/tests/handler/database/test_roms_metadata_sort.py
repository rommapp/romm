"""Ordering the gallery by a `roms_metadata` field.

`roms_metadata` is a thin view over STORED generated columns on `roms`
(migration 0098). Resolving one of its columns as the sort key used to join the
view back in, which re-joins `roms` to itself and leaves the sort key on the
joined table: the database cannot read that from an index, so it filesorts the
whole library on every page. The generated columns are indexed on `roms`, so
these tests pin both the ordering results and the query reading them directly.

NULL sort keys (unmatched roms) land last on every engine and both directions.
The ascending sort reads that placement off the materialized `_unset` flag,
since no index can serve the `ORDER BY <column> IS NULL` that emulated it.
"""

import pytest
import sqlalchemy as sa
from tests.handler.database.conftest import (
    MARIADB_DIALECT,
    POSTGRESQL_DIALECT,
    compile_sql,
)

from config import ROMM_DB_DRIVER
from handler.database import db_rom_handler
from handler.database.base_handler import sync_engine
from handler.database.rom_filters import RomFilterParams
from models.platform import Platform
from models.rom import Rom
from models.user import User
from utils.database import (
    SORTABLE_NULLABLE_ROM_COLUMNS,
    rom_desc_index_name,
    rom_sort_index_name,
    rom_unset_flag_column,
)


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
    return [rom.name or "" for rom in db_rom_handler.get_roms_scalar(**kwargs)]


class TestMetadataSortQueryShape:
    """The sort key has to be a `roms` column for its index to be usable."""

    @pytest.mark.parametrize(
        ("order_by", "expected_column"),
        [
            ("first_release_date", "generated_first_release_date"),
            ("average_rating", "generated_average_rating"),
            ("hltb_main_story", "generated_hltb_main_story"),
        ],
    )
    def test_orders_by_the_indexed_unset_flag_then_the_value(
        self, order_by: str, expected_column: str
    ):
        query, sort_key = db_rom_handler.get_roms_query(order_by=order_by)
        sql = str(query)

        # Both terms are columns of `idx_roms_<column>_sort`, in its order.
        assert (
            f"ORDER BY roms.{expected_column}_unset, roms.{expected_column} ASC"
        ) in sql
        assert "IS NULL" not in sql.split("ORDER BY")[-1]
        assert sort_key.column is getattr(Rom, expected_column)
        # `Rom.metadatum` is a `lazy="joined"` eager load, so one join to the
        # view is expected; the sort must not add a second one.
        assert sql.count("JOIN roms_metadata") == 1

    @pytest.mark.parametrize(
        ("dialect", "expected"),
        [
            (
                MARIADB_DIALECT,
                "ORDER BY roms.generated_player_count IS NULL, "
                "roms.generated_player_count ASC",
            ),
            (
                POSTGRESQL_DIALECT,
                "ORDER BY roms.generated_player_count ASC NULLS LAST",
            ),
        ],
    )
    def test_sort_without_a_flag_still_emulates_nulls_last(
        self, dialect: sa.Dialect, expected: str
    ):
        """`player_count` carries no flag; the gallery does not sort on it."""
        query, sort_key = db_rom_handler.get_roms_query(order_by="player_count")

        assert expected in compile_sql(query, dialect)
        assert sort_key.column is Rom.generated_player_count

    # One dialect matrix for the shared NULL-placement block; the rom_user
    # family proves its branch separately through the NULLIF shape test.
    # Every spelling here matches an index, so none of them filesorts.
    @pytest.mark.parametrize(
        ("dialect", "order_dir", "expected"),
        [
            (
                MARIADB_DIALECT,
                "asc",
                "roms.generated_first_release_date_unset, "
                "roms.generated_first_release_date ASC",
            ),
            (MARIADB_DIALECT, "desc", "roms.generated_first_release_date DESC"),
            (
                POSTGRESQL_DIALECT,
                "asc",
                "roms.generated_first_release_date_unset, "
                "roms.generated_first_release_date ASC",
            ),
            (
                POSTGRESQL_DIALECT,
                "desc",
                "roms.generated_first_release_date DESC NULLS LAST",
            ),
        ],
    )
    def test_null_placement_per_dialect(
        self, dialect: sa.Dialect, order_dir: str, expected: str
    ):
        query, _ = db_rom_handler.get_roms_query(
            order_by="first_release_date", order_dir=order_dir
        )
        order_sql = compile_sql(query, dialect).split("ORDER BY")[-1]

        assert order_sql.strip().startswith(expected)
        # Nothing computes NULL placement per row any more.
        assert "IS NULL" not in order_sql

    @pytest.mark.parametrize(
        ("dialect", "order_dir", "expected"),
        [
            (
                MARIADB_DIALECT,
                "asc",
                "roms.generated_player_count IS NULL, "
                "roms.generated_player_count ASC, MATCH(",
            ),
            (MARIADB_DIALECT, "desc", "roms.generated_player_count DESC, MATCH("),
            (
                POSTGRESQL_DIALECT,
                "asc",
                "roms.generated_player_count ASC NULLS LAST, roms.id ASC",
            ),
            (
                POSTGRESQL_DIALECT,
                "desc",
                "roms.generated_player_count DESC NULLS LAST, roms.id DESC",
            ),
        ],
    )
    def test_search_relevance_follows_the_null_placement_terms(
        self, dialect: sa.Dialect, order_dir: str, expected: str
    ):
        """Relevance only ranks on the FULLTEXT engines, after the explicit sort."""
        query, _ = db_rom_handler.get_roms_query(
            order_by="player_count", order_dir=order_dir, search_term="final fantasy"
        )

        assert compile_sql(query, dialect).split("ORDER BY ")[-1].startswith(expected)

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
            query=query,
            filters=RomFilterParams(group_by_meta_id=True),
            order_by="first_release_date",
        )
        sql = str(grouped)

        # Roms-side keys stay on the representative: aggregating one would
        # push the dedup window off its covering index.
        assert "group_sort_value" not in sql
        assert (
            "ORDER BY roms.generated_first_release_date_unset, "
            "roms.generated_first_release_date ASC"
        ) in sql


class TestSortIndexes:
    """The indexes the orderings above are shaped to read."""

    @pytest.fixture
    def roms_indexes(self) -> dict[str, list[str]]:
        with sync_engine.connect() as connection:
            return {
                index["name"]: [c for c in index["column_names"] if c]
                for index in sa.inspect(connection).get_indexes("roms")
                if index["name"]
            }

    @pytest.fixture
    def roms_index_sorting(self) -> dict[str, dict[str, tuple[str, ...]]]:
        with sync_engine.connect() as connection:
            return {
                index["name"]: {
                    column: tuple(order)
                    for column, order in (index.get("column_sorting") or {}).items()
                }
                for index in sa.inspect(connection).get_indexes("roms")
                if index["name"]
            }

    @pytest.mark.parametrize("column", SORTABLE_NULLABLE_ROM_COLUMNS)
    def test_ascending_sort_is_indexed_through_the_tiebreak(
        self, roms_indexes: dict[str, list[str]], column: str
    ):
        assert roms_indexes.get(rom_sort_index_name(column)) == [
            rom_unset_flag_column(column),
            column,
            "id",
        ]

    @pytest.mark.parametrize("column", SORTABLE_NULLABLE_ROM_COLUMNS)
    def test_descending_index_exists_only_on_postgresql(
        self, roms_indexes: dict[str, list[str]], column: str
    ):
        """`AUTOGENERATE_EXEMPT_INDEX_NAMES` hides these from the drift check,
        so nothing else would notice them going missing."""
        expected = [column, "id"] if ROMM_DB_DRIVER == "postgresql" else None
        assert roms_indexes.get(rom_desc_index_name(column)) == expected

    @pytest.mark.skipif(
        ROMM_DB_DRIVER != "postgresql", reason="only PostgreSQL parses the spelling"
    )
    @pytest.mark.parametrize("column", SORTABLE_NULLABLE_ROM_COLUMNS)
    def test_descending_index_spells_out_its_order(
        self, roms_index_sorting: dict[str, dict[str, tuple[str, ...]]], column: str
    ):
        """A default ascending index reflects the same columns and serves nothing."""
        assert roms_index_sorting[rom_desc_index_name(column)] == {
            column: ("desc", "nulls_last"),
            "id": ("desc",),
        }

    @pytest.mark.parametrize("column", SORTABLE_NULLABLE_ROM_COLUMNS)
    def test_ascending_index_takes_the_engine_default_order(
        self, roms_index_sorting: dict[str, dict[str, tuple[str, ...]]], column: str
    ):
        """Ascending is the direction the handler emits, so nothing is spelled out."""
        assert roms_index_sorting[rom_sort_index_name(column)] == {}


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

    @pytest.mark.parametrize(
        ("order_dir", "expected"),
        [
            ("asc", ["final fantasy solo", "final fantasy two", "final fantasy four"]),
            ("desc", ["final fantasy four", "final fantasy two", "final fantasy solo"]),
        ],
    )
    def test_search_ranks_after_the_sort(
        self, platform: Platform, order_dir: str, expected: list[str]
    ):
        # `player_count` falls back to "1", so "solo" needs no metadata.
        _make_rom(platform, "final fantasy four", igdb_metadata={"player_count": "4"})
        _make_rom(platform, "final fantasy solo")
        _make_rom(platform, "final fantasy two", igdb_metadata={"player_count": "2"})
        _make_rom(platform, "zelda", igdb_metadata={"player_count": "3"})

        assert (
            _ordered_names(
                order_by="player_count",
                order_dir=order_dir,
                search_term="final fantasy",
            )
            == expected
        )

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

    @pytest.mark.parametrize(
        ("column", "metadata"),
        [
            (
                "generated_first_release_date",
                {"igdb_metadata": {"first_release_date": "1569369600"}},
            ),
            ("generated_average_rating", {"igdb_metadata": {"total_rating": "80"}}),
            (
                "generated_hltb_main_story",
                {"hltb_metadata": {"main_story": "3600"}},
            ),
        ],
    )
    def test_unset_flag_tracks_its_value_column(
        self, platform: Platform, column: str, metadata: dict[str, dict[str, str]]
    ):
        """The sort's NULL placement rests on the flag, so it has to agree
        with the value it stands for."""
        matched = _make_rom(platform, "matched", **metadata)
        unmatched = _make_rom(platform, "unmatched")

        for rom_id, unset in ((matched.id, False), (unmatched.id, True)):
            rom = db_rom_handler.get_rom(rom_id)
            assert rom is not None
            assert (getattr(rom, column) is None) is unset
            assert getattr(rom, f"{column}_unset") is unset
