"""Loading a page's rows by id, without the filters or the sibling grouping."""

from sqlalchemy.dialects import postgresql
from tests.conftest import engine  # noqa: F401  (loads the test database setup)

from handler.database import db_rom_handler
from handler.database.rom_filters import RomFilterParams

PAGE_IDS = [11, 22, 33]


def _sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    ).lower()


def _page_rows_sql(user_id: int | None = 1, include_file_stats: bool = True) -> str:
    query, sort_key = db_rom_handler.get_roms_query(order_by="name", user_id=user_id)
    return _sql(
        db_rom_handler.get_page_rows_query(
            query,
            PAGE_IDS,
            sort_key=sort_key,
            order_by="name",
            order_dir="asc",
            user_id=user_id,
            include_file_stats=include_file_stats,
        )
    )


def test_the_grouped_query_does_rank_the_library():
    """The yardstick: grouping puts a window over every rom, so the next tests mean something."""
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
    assert "row_number()" not in _page_rows_sql()


def test_loading_a_page_is_limited_to_its_ids():
    assert "roms.id in (11, 22, 33)" in _page_rows_sql()


def test_loading_a_page_keeps_the_hidden_roms_filter():
    assert "rom_user.hidden" in _page_rows_sql(user_id=1)


def test_loading_a_page_keeps_the_status_the_ids_were_picked_with():
    query, sort_key = db_rom_handler.get_roms_query(order_by="name", user_id=1)
    sql = _sql(
        db_rom_handler.get_page_rows_query(
            query,
            PAGE_IDS,
            sort_key=sort_key,
            order_by="name",
            order_dir="asc",
            user_id=1,
            filters=RomFilterParams(statuses=["hidden"]),
        )
    )

    assert "rom_user.hidden is true" in sql
    assert "rom_user.hidden is false" not in sql


def test_loading_a_page_keeps_the_file_stats_the_serializer_reads():
    assert "rom_files" in _page_rows_sql(include_file_stats=True)
