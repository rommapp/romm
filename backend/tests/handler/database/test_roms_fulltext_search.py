from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Dialect
from tests.sql_dialects import MARIADB_DIALECT, POSTGRESQL_DIALECT, compile_sql

from handler.database import db_rom_handler, roms_handler
from models.rom import Rom
from utils.fulltext import DEFAULT_FULLTEXT_SETTINGS


@pytest.mark.parametrize(
    ("dialect", "like_count", "has_match"),
    [(MARIADB_DIALECT, 3, True), (POSTGRESQL_DIALECT, 9, False)],
)
def test_search_keeps_the_fulltext_index_for_indexable_words(
    dialect: Dialect, like_count: int, has_match: bool
):
    with patch.object(
        roms_handler, "fulltext_settings", return_value=DEFAULT_FULLTEXT_SETTINGS
    ):
        query = db_rom_handler._filter_by_search_term(select(Rom.id), "final fantasy 7")

    sql = compile_sql(query, dialect, literal_binds=True)

    assert ("AGAINST ('+final* +fantasy*' IN BOOLEAN MODE)" in sql) is has_match
    # MariaDB checks only "7" by LIKE; PostgreSQL checks every word.
    assert sql.count("LIKE") == like_count


def test_search_uses_like_alone_while_the_settings_are_unreadable():
    with patch.object(roms_handler, "fulltext_settings", return_value=None):
        query = db_rom_handler._filter_by_search_term(select(Rom.id), "final fantasy")

    sql = compile_sql(query, MARIADB_DIALECT, literal_binds=True)

    assert "+final*" not in sql
    assert sql.count("LIKE") == 6
