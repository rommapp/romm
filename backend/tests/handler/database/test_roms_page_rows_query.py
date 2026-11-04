"""Loading a page's rows by id, without the filters or the sibling grouping."""

from typing import Any

from sqlalchemy import Select
from tests.conftest import engine  # noqa: F401  (loads the test database setup)
from tests.sql_dialects import POSTGRESQL_DIALECT, compile_sql

from handler.auth.rom_visibility import RomVisibilityFilter
from handler.database import db_rom_handler
from handler.database.rom_filters import RomFilterParams

PAGE_IDS = [11, 22, 33]


def _sql(statement: Select[Any]) -> str:
    return compile_sql(statement, POSTGRESQL_DIALECT, literal_binds=True).lower()


def test_the_grouped_query_does_rank_the_library():
    """Grouping puts a window over every rom, which the page-row tests below must not."""
    query, sort_key = db_rom_handler.get_roms_query(order_by="name", user_id=1)
    grouped = db_rom_handler.filter_roms(
        query=query,
        filters=RomFilterParams(group_by_meta_id=True),
        sort_key=sort_key,
        order_by="name",
        user_id=1,
    )

    assert "row_number()" in _sql(grouped)


def test_loading_a_page_does_not_rank_the_library():
    assert "row_number()" not in _sql(db_rom_handler.get_page_rows_query(PAGE_IDS))


def test_loading_a_page_is_limited_to_its_ids():
    assert "roms.id in (11, 22, 33)" in _sql(
        db_rom_handler.get_page_rows_query(PAGE_IDS)
    )


def test_loading_a_page_does_not_refilter_on_rom_user():
    assert "rom_user" not in _sql(db_rom_handler.get_page_rows_query(PAGE_IDS))


def test_loading_a_page_keeps_the_visibility_filter():
    visibility = RomVisibilityFilter(hidden_platform_ids=frozenset({7}))
    sql = _sql(db_rom_handler.get_page_rows_query(PAGE_IDS, visibility=visibility))

    assert "roms.platform_id not in (7)" in sql


def test_loading_a_page_keeps_the_file_stats_the_serializer_reads():
    assert "rom_files" in _sql(
        db_rom_handler.get_page_rows_query(PAGE_IDS, include_file_stats=True)
    )
