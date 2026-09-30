from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from handler.database import db_rom_handler, roms_handler
from handler.database.base_handler import sync_engine
from handler.database.roms_handler import (
    DEFAULT_FULLTEXT_SETTINGS,
    FULLTEXT_STOPWORDS,
    FulltextSettings,
    _stopword_table,
    fulltext_settings,
)
from utils.database import is_mariadb, is_mysql

IS_FULLTEXT_ENGINE = is_mysql(sync_engine) or is_mariadb(sync_engine)


@pytest.fixture(autouse=True)
def fresh_settings() -> Iterator[None]:
    roms_handler._server_fulltext_settings.cache_clear()
    yield
    roms_handler._server_fulltext_settings.cache_clear()


def _mariadb_engine() -> MagicMock:
    engine = MagicMock()
    engine.name = "mariadb"
    engine.engine = engine
    return engine


def _engine_returning(
    min_token_size: int, stopwords_enabled: int, server_table: str | None
) -> MagicMock:
    engine = _mariadb_engine()
    conn = engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.one.return_value = (
        min_token_size,
        84,
        stopwords_enabled,
        server_table,
    )
    conn.scalars.return_value.all.return_value = ["Foo", "bar", None]
    return engine


@pytest.mark.skipif(not IS_FULLTEXT_ENGINE, reason="InnoDB full-text only")
def test_reads_the_servers_settings():
    with sync_engine.connect() as conn:
        min_token_size = conn.execute(
            text("SELECT @@innodb_ft_min_token_size")
        ).scalar_one()

    settings = fulltext_settings()

    assert settings.min_token_size == min_token_size
    assert "the" in settings.stopwords


@pytest.mark.skipif(IS_FULLTEXT_ENGINE, reason="PostgreSQL has no FULLTEXT index")
def test_postgresql_uses_the_defaults():
    assert fulltext_settings() == DEFAULT_FULLTEXT_SETTINGS


def test_falls_back_and_retries_when_the_server_is_unreachable():
    engine = _mariadb_engine()
    engine.connect.side_effect = OperationalError("SELECT", {}, Exception("2013"))

    with patch.object(roms_handler, "sync_engine", engine):
        assert fulltext_settings() == DEFAULT_FULLTEXT_SETTINGS
        assert fulltext_settings() == DEFAULT_FULLTEXT_SETTINGS

    assert engine.connect.call_count == 2


def test_keeps_the_token_sizes_when_the_stopwords_are_unreadable():
    engine = _engine_returning(4, 1, None)
    conn = engine.connect.return_value.__enter__.return_value
    conn.scalars.side_effect = OperationalError("SELECT", {}, Exception("1227"))

    with patch.object(roms_handler, "sync_engine", engine):
        settings = fulltext_settings()

    assert settings == FulltextSettings(4, 84, FULLTEXT_STOPWORDS)


def test_reads_a_custom_stopword_table():
    engine = _engine_returning(2, 1, "romm/stopwords")

    with patch.object(roms_handler, "sync_engine", engine):
        settings = fulltext_settings()

    conn = engine.connect.return_value.__enter__.return_value
    assert "FROM `romm`.`stopwords`" in str(conn.scalars.call_args.args[0])
    assert settings == FulltextSettings(2, 84, frozenset({"foo", "bar"}))


def test_disabled_stopwords_leave_none():
    with patch.object(roms_handler, "sync_engine", _engine_returning(3, 0, None)):
        assert fulltext_settings() == FulltextSettings(3, 84, frozenset())


def test_stopword_table_quotes_each_part():
    assert _stopword_table("romm/stop`words") == "`romm`.`stop``words`"


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("final fantasy 7", (["final", "fantasy"], ["7"])),
        ("the legend", (["legend"], ["the"])),
        # InnoDB reads "dr." as the 2-letter token "dr".
        ("dr. mario", (["mario"], ["dr."])),
        ("pokemon: red", (["pokemon", "red"], [])),
        ("spider-man x-2", (["spider", "man"], ["x-2"])),
        ("mario's", (["mario's"], [])),
        ("a" * 85, ([], ["a" * 85])),
    ],
)
def test_split_fulltext_words(term: str, expected: tuple[list[str], list[str]]):
    with patch.object(
        roms_handler, "fulltext_settings", return_value=DEFAULT_FULLTEXT_SETTINGS
    ):
        assert db_rom_handler._split_fulltext_words(term) == expected
