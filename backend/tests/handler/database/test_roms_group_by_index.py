"""The "Group ROMs" dedup window and the index that has to cover it.

Grouping collapses versions of the same game into one gallery entry with a
window function. The window materializes a narrow subquery first, because
carrying the wide `roms` row (every provider's raw metadata) through the window
spills its sort to disk. That narrowing only pays off if the index carries every
column the subquery reads: a covering index is all-or-nothing, so one missing
column drops the plan to a full table scan.

`idx_roms_sibling_cover` was added in 0090 for the `sibling_roms` self-join and
did not cover `flashpoint_id` or `fs_name_no_ext`, which the window needs for
its partition tail and its sort tiebreaker. The gallery issues the grouped query
up to four times per page load (page, count, char index, id index), so the scan
was paid four times over. 0107 widened the index to close the gap.

The failure mode is silent, and adding a metadata provider is the way back into
it: a new id column joins the window's COALESCE chain, the index does not follow
it, and the gallery quietly returns to full scans.
"""

from sqlalchemy import inspect
from sqlalchemy.sql import Subquery
from sqlalchemy.sql.expression import Select
from tests.conftest import engine

from handler.database import db_rom_handler
from models.rom import Rom

INDEX_COLUMNS = [
    "platform_id",
    "igdb_id",
    "moby_id",
    "ss_id",
    "launchbox_id",
    "ra_id",
    "hasheous_id",
    "tgdb_id",
    "flashpoint_id",
    "fs_name_no_ext",
    "id",
]


def _subqueries(clause, found: list[Subquery] | None = None) -> list[Subquery]:
    found = found if found is not None else []
    for child in clause.get_children():
        if isinstance(child, Subquery):
            found.append(child)
            _subqueries(child.element, found)
        elif hasattr(child, "get_children"):
            _subqueries(child, found)
    return found


def _dedup_window_columns() -> set[str]:
    """The `roms` columns the grouped query materializes for its window."""
    query, _ = db_rom_handler.get_roms_query()
    grouped = db_rom_handler.filter_roms(query=query, group_by_meta_id=True)

    for subquery in _subqueries(grouped):
        if not isinstance(subquery.element, Select):
            continue
        columns = {
            column.name
            for column in subquery.element.selected_columns
            if getattr(column, "table", None) is Rom.__table__
        }
        if columns:
            return columns

    raise AssertionError("the grouped query no longer materializes a roms subquery")


class TestSiblingCoverIndex:
    def test_migrations_create_covering_index(self):
        indexes = [
            index["column_names"] for index in inspect(engine).get_indexes("roms")
        ]

        assert INDEX_COLUMNS in indexes


class TestGroupByMetaIdCoverage:
    def test_dedup_window_reads_only_covered_columns(self):
        assert _dedup_window_columns() <= set(INDEX_COLUMNS)

    def test_dedup_window_excludes_the_wide_metadata_columns(self):
        assert not {
            column for column in _dedup_window_columns() if column.endswith("_metadata")
        }
